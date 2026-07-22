"""Iteration 12 tests — shipped-this-week activity endpoint + completed_at.

Covers:
  - GET /api/activity/weekly response shape + auth guard (401 unauth)
  - Newly-registered user has shipped_this_week == 0
  - PATCH /api/next-steps/{id} done=true stamps completed_at; done=false clears it
  - Weekly count reflects toggled steps accurately (steps outside 7d window excluded)
  - Rescan preservation: completed_at survives the same _run_scan preservation
    logic (simulated at DB level by replicating the completed_at_map keyed on
    normalized step text — see server._run_scan lines ~1140-1166).
"""
import os
import sys
import uuid
import asyncio
from datetime import datetime, timedelta, timezone

import pytest
import requests

# Ensure we can talk to Mongo the same way the app does.
sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


# ---------- helpers ---------------------------------------------------------

def _register():
    email = f"TEST_it12_{uuid.uuid4().hex[:10]}@example.com"
    s = requests.Session()
    r = s.post(f"{API}/auth/register", json={
        "email": email, "password": "correct-horse-battery-staple", "name": "T"
    })
    assert r.status_code == 200, f"register failed {r.status_code} {r.text}"
    body = r.json()
    return s, email, body["user_id"]


async def _mongo():
    client = AsyncIOMotorClient(MONGO_URL)
    return client, client[DB_NAME]


def _iso(dt):
    return dt.isoformat()


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if not asyncio.get_event_loop().is_running() else asyncio.run(coro)


# ---------- fixtures --------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    async def _c():
        client, d = await _mongo()
        # cleanup by TEST_it12 emails
        users = [u async for u in d.users.find({"email": {"$regex": "TEST_it12_"}}, {"user_id": 1})]
        uids = [u["user_id"] for u in users]
        if uids:
            await d.next_steps.delete_many({"user_id": {"$in": uids}})
            await d.projects.delete_many({"user_id": {"$in": uids}})
            await d.user_sessions.delete_many({"user_id": {"$in": uids}})
            await d.users.delete_many({"user_id": {"$in": uids}})
        client.close()
    try:
        asyncio.run(_c())
    except Exception as e:
        print(f"cleanup error: {e}")


# ---------- 1) shape + auth guard -------------------------------------------

class TestActivityWeeklyShapeAndAuth:
    def test_401_when_unauth(self):
        r = requests.get(f"{API}/activity/weekly")
        assert r.status_code == 401, f"expected 401 got {r.status_code} {r.text}"

    def test_new_user_zero(self):
        s, email, uid = _register()
        r = s.get(f"{API}/activity/weekly")
        assert r.status_code == 200
        data = r.json()
        assert data == {"shipped_this_week": 0, "threshold": 3, "window_days": 7}


# ---------- 2) PATCH toggle stamps + unstamps completed_at ------------------

class TestToggleCompletedAt:
    def _seed_step(self, uid, project_id="proj_t12", done=False, completed_at=None, text="Add tests"):
        async def _s():
            client, d = await _mongo()
            step_id = f"step_{uuid.uuid4().hex[:10]}"
            doc = {
                "id": step_id,
                "user_id": uid,
                "project_id": project_id,
                "text": text,
                "weight": 5,
                "order": 1,
                "done": done,
                "completed_at": completed_at,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await d.next_steps.insert_one(doc)
            # ensure project doc exists so PATCH's _project_to_out doesn't crash
            await d.projects.update_one(
                {"id": project_id, "user_id": uid},
                {"$setOnInsert": {
                    "id": project_id, "user_id": uid, "name": "t",
                    "full_name": "t/t", "github_repo_id": 1,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }},
                upsert=True,
            )
            client.close()
            return step_id
        return asyncio.run(_s())

    def _get_step(self, step_id):
        async def _g():
            client, d = await _mongo()
            doc = await d.next_steps.find_one({"id": step_id}, {"_id": 0})
            client.close()
            return doc
        return asyncio.run(_g())

    def test_done_true_stamps_completed_at_and_activity_reflects(self):
        s, email, uid = _register()
        step_id = self._seed_step(uid)
        r = s.patch(f"{API}/next-steps/{step_id}", json={"done": True})
        assert r.status_code == 200, r.text
        doc = self._get_step(step_id)
        assert doc["done"] is True
        assert doc["completed_at"], "completed_at should be set on done=true"
        # activity should now show 1
        r2 = s.get(f"{API}/activity/weekly")
        assert r2.status_code == 200
        assert r2.json()["shipped_this_week"] == 1

    def test_done_false_clears_completed_at(self):
        s, email, uid = _register()
        step_id = self._seed_step(uid, done=True,
                                   completed_at=_iso(datetime.now(timezone.utc)))
        r = s.patch(f"{API}/next-steps/{step_id}", json={"done": False})
        assert r.status_code == 200, r.text
        doc = self._get_step(step_id)
        assert doc["done"] is False
        assert doc["completed_at"] is None, "completed_at should clear on done=false"
        r2 = s.get(f"{API}/activity/weekly")
        assert r2.json()["shipped_this_week"] == 0

    def test_activity_excludes_old_completions_beyond_7d(self):
        s, email, uid = _register()
        old = _iso(datetime.now(timezone.utc) - timedelta(days=10))
        recent = _iso(datetime.now(timezone.utc) - timedelta(days=1))
        self._seed_step(uid, done=True, completed_at=old, text="old-1")
        self._seed_step(uid, done=True, completed_at=recent, text="new-1")
        self._seed_step(uid, done=True, completed_at=recent, text="new-2")
        r = s.get(f"{API}/activity/weekly")
        assert r.status_code == 200
        assert r.json()["shipped_this_week"] == 2

    def test_activity_threshold_and_window_days_constants(self):
        s, email, uid = _register()
        for i in range(3):
            self._seed_step(uid, done=True,
                            completed_at=_iso(datetime.now(timezone.utc)),
                            text=f"seed-{i}")
        r = s.get(f"{API}/activity/weekly")
        j = r.json()
        assert j["threshold"] == 3
        assert j["window_days"] == 7
        assert j["shipped_this_week"] == 3


# ---------- 3) Rescan preservation (simulated) ------------------------------

class TestRescanPreservation:
    """Simulate the completed_at_map preservation logic used by both
    _run_scan (~L1140) and _job_rescan_stale_projects (~L1961). We can't
    exercise the full scan (requires GitHub API + LLM), but we replicate
    the same preservation code path against real Mongo docs. This guards
    against regressions in the shape of the preserved data.
    """

    def test_completed_at_persists_across_delete_and_rebuild(self):
        async def _t():
            client, d = await _mongo()
            uid = f"test-user-{uuid.uuid4().hex[:10]}"
            pid = f"proj_rescan_{uuid.uuid4().hex[:6]}"
            original_completed = _iso(datetime.now(timezone.utc) - timedelta(days=2))
            await d.next_steps.insert_one({
                "id": f"step_{uuid.uuid4().hex[:10]}",
                "user_id": uid,
                "project_id": pid,
                "text": "  Add README badges  ",  # will be normalized to lower+strip
                "weight": 5,
                "order": 1,
                "done": True,
                "completed_at": original_completed,
                "created_at": _iso(datetime.now(timezone.utc)),
            })

            # === Mirror server._run_scan L1140-1166 ===
            old_steps = [s async for s in d.next_steps.find(
                {"project_id": pid}, {"_id": 0},
            )]
            done_texts = {s["text"].strip().lower() for s in old_steps if s.get("done")}
            completed_at_map = {
                s["text"].strip().lower(): s.get("completed_at")
                for s in old_steps
                if s.get("done") and s.get("completed_at")
            }
            await d.next_steps.delete_many({"project_id": pid})
            new_ai_steps = [
                {"text": "Add README badges", "weight": 5, "order": 1},  # identical after normalize
                {"text": "Write CI pipeline", "weight": 8, "order": 2},  # brand new
            ]
            new_docs = []
            for i, step in enumerate(new_ai_steps, start=1):
                key = step["text"].strip().lower()
                is_done = key in done_texts
                new_docs.append({
                    "id": f"step_{uuid.uuid4().hex[:10]}",
                    "user_id": uid,
                    "project_id": pid,
                    "text": step["text"],
                    "weight": step["weight"],
                    "order": step.get("order", i),
                    "done": is_done,
                    "completed_at": completed_at_map.get(key) if is_done else None,
                    "created_at": _iso(datetime.now(timezone.utc)),
                })
            await d.next_steps.insert_many(new_docs)

            # Assert: previously-done step retains original completed_at exactly.
            preserved = await d.next_steps.find_one({"text": "Add README badges"}, {"_id": 0})
            fresh = await d.next_steps.find_one({"text": "Write CI pipeline"}, {"_id": 0})

            # cleanup
            await d.next_steps.delete_many({"project_id": pid})
            client.close()

            assert preserved is not None
            assert preserved["done"] is True, "done flag should carry over"
            assert preserved["completed_at"] == original_completed, \
                "completed_at must be preserved bit-for-bit across rescan"
            assert fresh is not None
            assert fresh["done"] is False
            assert fresh["completed_at"] is None

        asyncio.run(_t())
