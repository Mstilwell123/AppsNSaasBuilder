"""Postgres data-access layer for AppsNSaasBuilder (Option A migration).

Drop-in-ish replacement for the Motor `db` global. The existing code calls
`db.<collection>.<op>(...)`; this module exposes the same surface backed by
asyncpg so endpoint logic is unchanged.

Supported ops (the only 7 the app uses):
    find_one(filter, projection=None, sort=None)
    find(filter, projection=None)  -> async cursor: .sort(k,d)/.sort([(k,d)])/.to_list(length)
    insert_one(doc) / insert_many([docs])
    update_one(filter, update, upsert=False)
    delete_many(filter)
    count_documents(filter)

Filter translation (the exact operators the code uses):
    {field: value}            -> field = value
    {field: {"$gte": v}}      -> field >= v
    {field: {"$lt": v}}       -> field < v
    {field: {"$ne": v}}       -> field IS DISTINCT FROM v  (NULL-safe)
    {field: {"$exists": b}}   -> field IS [NOT] NULL
    {field: {"$in": [..]}}    -> field = ANY(..)
    {email: {"$regex": p}}    -> email ILIKE p (only used in tests)

Update translation:
    {"$set": {...}}           -> SET col=val, ...
    {"$setOnInsert": {...}}   -> (upsert path) values applied on INSERT
    {"$inc": {f: n}}          -> SET f = COALESCE(f,0) + n
    {"$unset": {f: ""}}       -> SET f = NULL

Values that are dict/list are stored as jsonb; ISO timestamp strings are passed
through (Postgres parses them into timestamptz columns).

Usage:
    from db_pg import init_db, db
    await init_db(DATABASE_URL)         # once at startup
    row = await db.users.find_one({"email": email})
"""
from __future__ import annotations

import json
import datetime as _dt
from typing import Any, Optional

import asyncpg

_pool: Optional[asyncpg.Pool] = None

# Columns that are jsonb in the schema (values must be json.dumps'd on write,
# and are returned already-parsed by asyncpg's jsonb codec -> keep as objects).
JSONB_COLS = {
    "languages", "commit_sparkline", "dimensions", "project_ids",
}


async def init_db(dsn: str, min_size: int = 1, max_size: int = 10) -> None:
    """Create the connection pool. Call once at startup."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(dsn, min_size=min_size, max_size=max_size)


async def close_db() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def _is_temporal(val: Any) -> bool:
    return isinstance(val, (_dt.datetime, _dt.date))


def _encode(col: str, val: Any) -> Any:
    """Encode a Python value for asyncpg binding based on target column type."""
    if val is None:
        return None
    if col in JSONB_COLS and isinstance(val, (dict, list)):
        return json.dumps(val)
    return val


def _build_where(filter_doc: dict, start_idx: int = 1):
    """Translate a Mongo-style filter into (sql_where, params). Returns ("TRUE", [])
    for an empty filter."""
    clauses, params = [], []
    idx = start_idx
    for field, cond in (filter_doc or {}).items():
        col = f'"{field}"'
        if isinstance(cond, dict):
            for op, v in cond.items():
                if op == "$gte":
                    clauses.append(f"{col} >= ${idx}"); params.append(_encode(field, v)); idx += 1
                elif op == "$gt":
                    clauses.append(f"{col} > ${idx}"); params.append(_encode(field, v)); idx += 1
                elif op == "$lt":
                    clauses.append(f"{col} < ${idx}"); params.append(_encode(field, v)); idx += 1
                elif op == "$lte":
                    clauses.append(f"{col} <= ${idx}"); params.append(_encode(field, v)); idx += 1
                elif op == "$ne":
                    if v is None:
                        clauses.append(f"{col} IS NOT NULL")
                    else:
                        clauses.append(f"{col} IS DISTINCT FROM ${idx}"); params.append(_encode(field, v)); idx += 1
                elif op == "$exists":
                    clauses.append(f"{col} IS {'NOT ' if v else ''}NULL")
                elif op == "$in":
                    vals = [_encode(field, x) for x in v]
                    clauses.append(f"{col} = ANY(${idx})"); params.append(vals); idx += 1
                elif op == "$regex":
                    # Mongo regex -> ILIKE substring (tests only use /^prefix/)
                    pat = str(v).lstrip("^").rstrip("$")
                    clauses.append(f"{col} ILIKE ${idx}"); params.append(f"%{pat}%"); idx += 1
                else:
                    raise ValueError(f"Unsupported filter operator {op}")
        else:
            if cond is None:
                clauses.append(f"{col} IS NULL")
            else:
                clauses.append(f"{col} = ${idx}"); params.append(_encode(field, cond)); idx += 1
    where = " AND ".join(clauses) if clauses else "TRUE"
    return where, params


def _projection_cols(projection: Optional[dict]) -> str:
    """Mongo projection {"_id": 0} (exclude) or {"a":1,"b":1} (include) -> SQL column list."""
    if not projection:
        return "*"
    # Exclude form: all values 0 -> we just return * (Mongo _id doesn't exist in PG anyway)
    if all(v == 0 for v in projection.values()):
        return "*"
    include = [f'"{k}"' for k, v in projection.items() if v]
    return ", ".join(include) if include else "*"


def _row_to_dict(rec: Optional[asyncpg.Record]) -> Optional[dict]:
    if rec is None:
        return None
    d = dict(rec)
    # asyncpg returns jsonb as str by default in some configs; parse if needed
    for k, v in list(d.items()):
        if k in JSONB_COLS and isinstance(v, str):
            try:
                d[k] = json.loads(v)
            except Exception:
                pass
        # timestamptz -> ISO string to match Mongo's stored ISO strings
        if isinstance(v, (_dt.datetime,)):
            d[k] = v.isoformat()
        elif isinstance(v, _dt.date):
            d[k] = v.isoformat()
    return d


class _Cursor:
    """Mimics Motor's async cursor for find()."""

    def __init__(self, table: str, filter_doc: dict, projection: Optional[dict]):
        self._table = table
        self._filter = filter_doc or {}
        self._projection = projection
        self._sorts: list[tuple[str, int]] = []

    def sort(self, key, direction: Optional[int] = None):
        # Accept .sort("field", -1) or .sort([("field", -1), ...])
        if isinstance(key, list):
            self._sorts.extend((k, d) for k, d in key)
        else:
            self._sorts.append((key, direction if direction is not None else 1))
        return self

    def _sql(self):
        where, params = _build_where(self._filter)
        cols = _projection_cols(self._projection)
        sql = f'SELECT {cols} FROM "{self._table}" WHERE {where}'
        if self._sorts:
            order = ", ".join(f'"{k}" {"DESC" if d < 0 else "ASC"}' for k, d in self._sorts)
            sql += f" ORDER BY {order}"
        return sql, params

    async def to_list(self, length: Optional[int] = None) -> list:
        sql, params = self._sql()
        if length:
            sql += f" LIMIT {int(length)}"
        async with _pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
        return [_row_to_dict(r) for r in rows]

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        sql, params = self._sql()
        async with _pool.acquire() as conn:
            async with conn.transaction():
                async for rec in conn.cursor(sql, *params):
                    yield _row_to_dict(rec)


class _Collection:
    def __init__(self, table: str):
        self._table = table

    async def find_one(self, filter_doc: dict = None, projection: Optional[dict] = None,
                       sort: Optional[list] = None, **_) -> Optional[dict]:
        where, params = _build_where(filter_doc or {})
        cols = _projection_cols(projection)
        sql = f'SELECT {cols} FROM "{self._table}" WHERE {where}'
        if sort:
            order = ", ".join(f'"{k}" {"DESC" if d < 0 else "ASC"}' for k, d in sort)
            sql += f" ORDER BY {order}"
        sql += " LIMIT 1"
        async with _pool.acquire() as conn:
            rec = await conn.fetchrow(sql, *params)
        return _row_to_dict(rec)

    def find(self, filter_doc: dict = None, projection: Optional[dict] = None, **_) -> _Cursor:
        return _Cursor(self._table, filter_doc or {}, projection)

    async def insert_one(self, doc: dict, **_):
        cols, vals, params = [], [], []
        for i, (k, v) in enumerate(doc.items(), start=1):
            cols.append(f'"{k}"')
            vals.append(f"${i}")
            params.append(_encode(k, v))
        sql = f'INSERT INTO "{self._table}" ({", ".join(cols)}) VALUES ({", ".join(vals)})'
        async with _pool.acquire() as conn:
            await conn.execute(sql, *params)
        return type("res", (), {"inserted_id": doc.get("id")})()

    async def insert_many(self, docs: list, **_):
        async with _pool.acquire() as conn:
            async with conn.transaction():
                for doc in docs:
                    cols, vals, params = [], [], []
                    for i, (k, v) in enumerate(doc.items(), start=1):
                        cols.append(f'"{k}"'); vals.append(f"${i}"); params.append(_encode(k, v))
                    sql = f'INSERT INTO "{self._table}" ({", ".join(cols)}) VALUES ({", ".join(vals)})'
                    await conn.execute(sql, *params)

    def _build_set(self, update: dict, start_idx: int = 1):
        sets, params = [], []
        idx = start_idx
        for k, v in (update.get("$set") or {}).items():
            sets.append(f'"{k}" = ${idx}'); params.append(_encode(k, v)); idx += 1
        for k, v in (update.get("$inc") or {}).items():
            sets.append(f'"{k}" = COALESCE("{k}", 0) + ${idx}'); params.append(v); idx += 1
        for k in (update.get("$unset") or {}).keys():
            sets.append(f'"{k}" = NULL')
        return sets, params, idx

    async def update_one(self, filter_doc: dict, update: dict, upsert: bool = False, **_):
        where, wparams = _build_where(filter_doc)
        if upsert:
            # Build an INSERT ... ON CONFLICT DO UPDATE. Need a conflict target:
            # use the equality fields of the filter as the insert base.
            base = {k: v for k, v in filter_doc.items() if not isinstance(v, dict)}
            insert_doc = dict(base)
            insert_doc.update(update.get("$setOnInsert") or {})
            insert_doc.update(update.get("$set") or {})
            cols = list(insert_doc.keys())
            col_sql = ", ".join(f'"{c}"' for c in cols)
            placeholders = ", ".join(f"${i+1}" for i in range(len(cols)))
            iparams = [_encode(c, insert_doc[c]) for c in cols]
            # conflict target: primary/unique key columns present in filter
            # (heuristic: use 'id' if present else 'user_id' else first key)
            conflict = "id" if "id" in base else ("user_id" if "user_id" in base else cols[0])
            set_parts, uparams, _ = self._build_set(update, start_idx=len(iparams) + 1)
            set_sql = ", ".join(set_parts) if set_parts else f'"{conflict}" = EXCLUDED."{conflict}"'
            sql = (f'INSERT INTO "{self._table}" ({col_sql}) VALUES ({placeholders}) '
                   f'ON CONFLICT ("{conflict}") DO UPDATE SET {set_sql}')
            async with _pool.acquire() as conn:
                await conn.execute(sql, *(iparams + uparams))
            return
        set_parts, sparams, _ = self._build_set(update, start_idx=len(wparams) + 1)
        if not set_parts:
            return
        sql = f'UPDATE "{self._table}" SET {", ".join(set_parts)} WHERE {where}'
        async with _pool.acquire() as conn:
            await conn.execute(sql, *(wparams + sparams))

    async def update_many(self, filter_doc: dict, update: dict, **_):
        # same as update_one (no upsert) — used rarely
        await self.update_one(filter_doc, update, upsert=False)

    async def delete_many(self, filter_doc: dict, **_):
        where, params = _build_where(filter_doc or {})
        sql = f'DELETE FROM "{self._table}" WHERE {where}'
        async with _pool.acquire() as conn:
            res = await conn.execute(sql, *params)
        # res like "DELETE 3"
        try:
            n = int(res.split()[-1])
        except Exception:
            n = 0
        return type("res", (), {"deleted_count": n})()

    async def delete_one(self, filter_doc: dict, **_):
        return await self.delete_many(filter_doc)

    async def count_documents(self, filter_doc: dict, **_) -> int:
        where, params = _build_where(filter_doc or {})
        sql = f'SELECT COUNT(*) AS c FROM "{self._table}" WHERE {where}'
        async with _pool.acquire() as conn:
            rec = await conn.fetchrow(sql, *params)
        return int(rec["c"]) if rec else 0


class _DB:
    """Attribute access: db.users -> _Collection('users')."""

    def __getattr__(self, name: str) -> _Collection:
        if name.startswith("_"):
            raise AttributeError(name)
        return _Collection(name)

    def __getitem__(self, name: str) -> _Collection:
        return _Collection(name)


# Module-level singleton mirroring `db` from Motor.
db = _DB()
