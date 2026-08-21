# AppsNSaasBuilder — Mongo → Postgres (Supabase) Migration Plan
**Path:** Option A — keep FastAPI, swap only the data layer. Backend hosted on Render.
**DB target:** new Supabase project (Postgres + service-role key, server-side only).
**Status:** PLAN — awaiting owner approval before any code is written.

---

## Why this is low-risk

- The app touches Mongo through **one global** `db = AsyncIOMotorClient(...)[DB_NAME]`.
- Only **7 operations** are used across all 63 endpoints:
  `find_one (36)`, `update_one (28)`, `find (28)`, `delete_many (19)`, `insert_one (16)`, `count_documents (5)`, `insert_many (2)`.
- **Zero business logic changes.** We replace *how rows are fetched/stored*, not *what the app does*.

The strategy: introduce a thin async **data-access layer (`db_pg.py`)** that exposes
the same conceptual operations the code uses today (`find_one`, `find`, `insert_one`,
`update_one`, `delete_many`, `count_documents`), backed by Postgres via `asyncpg`
(+ SQL composition). Endpoint code changes are limited to swapping the call shape —
Mongo filter dict → a small where-builder. No rewrites of scoring, billing, GitHub,
or cron logic.

---

## What changes (and what doesn't)

| Area | Change? | Detail |
|---|---|---|
| 20 Mongo collections → 20 Postgres tables | ✅ | `schema.sql` (already written) |
| Motor → asyncpg data layer | ✅ | new `db_pg.py`, ~150 lines |
| Mongo filter dicts → SQL where | ✅ | mechanical, per-endpoint |
| FastAPI app + 63 endpoints | ⚠️ touched, not rewritten | only the `db.` call sites |
| Scoring / readiness / LLM | ❌ | unchanged (`llm_providers.py` stays) |
| Stripe (SDK, webhooks, portal) | ❌ | unchanged — only its storage moves tables |
| GitHub OAuth + Fernet tokens | ❌ | unchanged — token stored in Postgres now |
| Custom auth (bcrypt + session cookies) | ❌ | stays custom (Option A); tables: `users`, `user_sessions` |
| APScheduler 3 cron jobs | ❌ | stays in FastAPI on Render |
| Frontend (React) | ❌ | unchanged; only `REACT_APP_BACKEND_URL` points at Render |

---

## Work breakdown (small, capped, verifiable increments)

**Sprint M0 — Provision Supabase (owner does logins, I do commands)**
1. Owner creates new Supabase project (I give deep-link + numbered clicks).
2. Owner pastes: `sbp_` personal access token + project ref + DB connection string.
3. I run `schema.sql` via the Management API (browser User-Agent header trick).
4. Verify: 20 tables exist via read-only SQL. **Done = tables present.**

**Sprint M1 — Data-access layer (`db_pg.py`)**
1. Add `asyncpg` to requirements; build `PG` class with the 7 operations.
2. Where-builder: translate the filter dicts the code actually uses
   (`{user_id: X}`, `{project_id: Y}`, `{session_token: Z}`, `{email: ...}`,
    `{score...}`) into parameterized SQL. No generic query engine — only the
    ~12 distinct filter shapes that exist.
3. Return rows as plain dicts (matching what endpoints expect today).
4. **Done = unit-test the layer against a local Postgres (or Supabase) with sample rows.**

**Sprint M2 — Port endpoints collection-by-collection (mechanical)**
Order chosen to prove value early and keep each PR small:
1. `users`, `user_sessions`, `password_reset_tokens`, `login_attempts` (auth works end-to-end first)
2. `projects`, `scores`, `next_steps`, `scans` (the core product loop)
3. `billing`, `payment_transactions` (Stripe storage)
4. `github_connections`, `github_oauth_states` (OAuth)
5. `stack_services`, `costs`, `ownership`, `documents`, `decisions`, `evidence`, `ideas`, `launch_checklist`
6. **Done = each sprint: the corresponding endpoints respond correctly against Postgres.**

**Sprint M3 — Cron + startup**
1. `_job_send_weekly_digests`, `_job_rescan_stale_projects`, `_job_lock_expired_trials`
   swap their `db.` calls; scheduler stays as-is.
2. Remove Motor/`MONGO_URL`; startup requires `DATABASE_URL` (fail fast if missing).
3. **Done = app boots on Postgres; cron jobs run against Supabase.**

**Sprint M4 — Verify + deploy to Render**
1. Port the **test suite's** DB seeding from pymongo → SQL (this also fixes the
   Windows `mongosh` portability bug as a side effect — we replace that subprocess
   cleanup with SQL too).
2. Run the suite green against Supabase (or a local Postgres for CI speed).
3. Deploy FastAPI to Render (`render.yaml` already exists), set `DATABASE_URL` +
   existing env vars, point frontend `REACT_APP_BACKEND_URL` at Render.
4. **Done = green tests + a reachable preview URL.**

---

## Data migration (existing users, if any)
The live site doesn't resolve and there's no indication of production data. If a
real Mongo with users exists, we add a one-shot `migrate_mongo_to_pg.py`:
read each collection → map `_id`→text id, ISO strings→timestamptz, embedded
arrays/objects→jsonb → insert. Idempotent (upsert by id). **Deferred until we know
there's data worth moving.**

---

## The 12 filter shapes the where-builder must support
(gathered from the code — this is the whole translation surface)
- `{user_id: X}` (most common)
- `{user_id: X, project_id: Y}` / `{project_id: Y}`
- `{id: X, user_id: Y}` / `{id: X}`
- `{email: lower}` (login/register/attempts)
- `{session_token: X}` (auth)
- `{token_hash: X}` (password reset)
- `{state: X}` (GitHub OAuth)
- `{github_repo_id: N}` + `{user_id: X, github_repo_id: N}` (track)
- `{score...}` sorting (`sort=[("scored_at", -1)]`, `sort("order", 1)`)
- `{created_at: {$gte/$lt: ...}}` (login-attempts window, digest, rescan stale)
- `{email: {$regex: ...}}` — only in test cleanup (we'll use SQL `ILIKE`)
- `{trial_ends_at: {$lt: now}, locked_at: {$exists:...}}` (trial-lock cron)

Operators needed: `$gte`, `$gt`, `$lte`, `$lt`, `$exists`, `$ne`, `$in`, `$regex`(→ILIKE).
Update operators: `$set`, `$setOnInsert`, `$inc`, `$unset`.

---

## Decisions I need from you (one at a time)
1. **Supabase project:** create it and paste the `sbp_` token + ref + DB connection string (I'll walk you through the clicks).
2. **Auth stays custom** (bcrypt + sessions) for Option A — confirm you're OK *not* moving to Supabase Auth in this pass. (Recommended: keep custom; less to break.)
3. **Test seeding:** OK to port the test suite's pymongo seeding → SQL in Sprint M4 (this is what also makes the suite Windows-green)?

---

## What I will NOT do without explicit approval
- Create/alter anything in a live Supabase project (needs your `sbp_` token).
- Deploy to Render or repoint any domain.
- Delete the Mongo code path until Postgres is proven green.
