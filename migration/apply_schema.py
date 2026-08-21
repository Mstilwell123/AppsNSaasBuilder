"""Sprint M0: discover the new Supabase project and apply schema.sql.

Steps (all via the Supabase Management API with a browser User-Agent — Cloudflare
blocks non-browser UAs):
  1. GET /v1/projects            -> list projects, let me pick the target ref
  2. POST /v1/projects/{ref}/database/query  -> run schema.sql
  3. verify the 20 tables exist

Token comes from env SUPABASE_ACCESS_TOKEN (never written to disk).
Optional SUPABASE_PROJECT_REF skips the list step.
"""
import os, sys, json, urllib.request, urllib.error, pathlib

TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "").strip()
REF = os.environ.get("SUPABASE_PROJECT_REF", "").strip()
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
BASE = "https://api.supabase.com"

if not TOKEN:
    print("ERROR: SUPABASE_ACCESS_TOKEN not set"); sys.exit(1)

def call(method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("User-Agent", UA)
    req.add_header("Content-Type", "application/json")
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data=data, timeout=30) as r:
            txt = r.read().decode()
            return r.status, (json.loads(txt) if txt else {})
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:800]
    except Exception as e:
        return -1, str(e)

# 1. discover ref if not provided
if not REF:
    st, proj = call("GET", "/v1/projects")
    print(f"[list projects] HTTP {st}")
    if st != 200:
        print("  ->", proj); sys.exit(1)
    items = proj if isinstance(proj, list) else proj.get("projects", [])
    for p in items:
        print(f"  - name={p.get('name')!r} ref={p.get('id') or p.get('ref')} region={p.get('region')} status={p.get('status')}")
    if len(items) == 1:
        REF = items[0].get("id") or items[0].get("ref")
        print(f"[auto-selected only project] ref={REF}")
    else:
        print("\nMultiple projects found. Re-run with SUPABASE_PROJECT_REF=<ref> for the new one.")
        sys.exit(2)
else:
    print(f"[using provided ref] {REF}")

# 2. apply schema
schema = pathlib.Path(r"C:/Users/stilw/app-review/migration/schema.sql").read_text(encoding="utf-8")
print(f"\n[applying schema] {len(schema)} chars to project {REF} ...")
st, res = call("POST", f"/v1/projects/{REF}/database/query", {"query": schema})
print(f"[schema apply] HTTP {st}")
if st not in (200, 201):
    print("  ->", res); sys.exit(1)
print("  -> schema applied OK")

# 3. verify tables
verify = """
select tablename from pg_catalog.pg_tables
where schemaname='public' order by tablename;
"""
st, res = call("POST", f"/v1/projects/{REF}/database/query", {"query": verify})
print(f"\n[verify tables] HTTP {st}")
print(res if st != 200 else json.dumps(res, indent=2)[:1500])
