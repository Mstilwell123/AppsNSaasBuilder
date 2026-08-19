"""Cross-user isolation tests — prove user A cannot access user B's projects, scores,
next-steps, or scans.

This is a regression guard: every project-scoped endpoint must filter by user_id.
If any endpoint leaks data across users, these tests fail.
"""
import os
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

from pymongo import MongoClient
mongo = MongoClient(MONGO_URL)
db = mongo[DB_NAME]


def _seed_user_and_session(prefix="TEST_ISO"):
    uid = f"{prefix}-user-{uuid.uuid4().hex[:8]}"
    token = f"TEST_session_{uuid.uuid4().hex}"
    now = datetime.now(timezone.utc)
    doc = {
        "user_id": uid,
        "email": f"TEST.{uid}@example.com",
        "name": "Isolation Test User",
        "picture": None,
        "password_hash": None,
        "trial_started_at": now.isoformat(),
        "trial_ends_at": (now + timedelta(days=7)).isoformat(),
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    db.users.insert_one(doc)
    db.user_sessions.insert_one({
        "user_id": uid,
        "session_token": token,
        "expires_at": (now + timedelta(days=7)).isoformat(),
        "created_at": now.isoformat(),
    })
    return uid, token


def _seed_project(user_id, name="iso-test"):
    pid = f"proj_iso_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    db.projects.insert_one({
        "id": pid,
        "user_id": user_id,
        "github_repo_id": 100 + hash(pid) % 10_000,
        "name": name,
        "full_name": f"iso/{name}",
        "private": False,
        "primary_language": "Python",
        "languages": {"Python": 1000},
        "stars": 1, "forks": 0, "open_issues": 0,
        "default_branch": "main",
        "live_url": None,
        "ci_status": "no_ci",
        "commit_sparkline": [1, 0, 2],
        "last_commit_at": now,
        "one_line_summary": "Isolation test project.",
        "added_at": now,
        "updated_at": now,
    })
    # Seed a score
    db.scores.insert_one({
        "id": f"score_iso_{uuid.uuid4().hex[:6]}",
        "user_id": user_id,
        "project_id": pid,
        "score": 42,
        "rationale": "Isolation test score.",
        "model": "test-model",
        "scored_at": now,
    })
    # Seed a next-step
    db.next_steps.insert_one({
        "id": f"step_iso_{uuid.uuid4().hex[:8]}",
        "user_id": user_id,
        "project_id": pid,
        "text": "Isolation test step",
        "weight": 3,
        "order": 1,
        "done": False,
        "completed_at": None,
        "created_at": now,
    })
    return pid


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def two_users():
    """Create user A (owns a project) and user B (should NOT access A's project)."""
    uid_a, token_a = _seed_user_and_session(prefix="TEST_ISO_A")
    uid_b, token_b = _seed_user_and_session(prefix="TEST_ISO_B")
    pid = _seed_project(uid_a)
    step = db.next_steps.find_one({"project_id": pid}, {"_id": 0})
    yield uid_a, token_a, uid_b, token_b, pid, step["id"]
    # Cleanup
    for uid in (uid_a, uid_b):
        db.projects.delete_many({"user_id": uid})
        db.scores.delete_many({"user_id": uid})
        db.next_steps.delete_many({"user_id": uid})
        db.scans.delete_many({"user_id": uid})
        db.user_sessions.delete_many({"user_id": uid})
        db.users.delete_many({"user_id": uid})


class TestCrossUserIsolation:
    """User B must NOT be able to read, modify, or delete user A's project data."""

    def test_get_project_returns_404_for_other_user(self, two_users):
        _, _, _, token_b, pid, _ = two_users
        r = requests.get(f"{API}/projects/{pid}", headers=auth(token_b))
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"

    def test_delete_project_returns_404_for_other_user(self, two_users):
        _, _, _, token_b, pid, _ = two_users
        r = requests.delete(f"{API}/projects/{pid}", headers=auth(token_b))
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
        # Verify project still exists for user A
        proj = db.projects.find_one({"id": pid})
        assert proj is not None, "Project was deleted by user B — isolation breach!"

    def test_scan_project_returns_404_for_other_user(self, two_users):
        _, _, _, token_b, pid, _ = two_users
        r = requests.post(f"{API}/projects/{pid}/scan", headers=auth(token_b))
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"

    def test_score_history_returns_404_for_other_user(self, two_users):
        _, _, _, token_b, pid, _ = two_users
        r = requests.get(f"{API}/projects/{pid}/scores", headers=auth(token_b))
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"

    def test_toggle_next_step_returns_404_for_other_user(self, two_users):
        _, _, _, token_b, _, step_id = two_users
        r = requests.patch(f"{API}/next-steps/{step_id}",
                           headers=auth(token_b),
                           json={"done": True})
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
        # Verify step was NOT modified
        step = db.next_steps.find_one({"id": step_id})
        assert step["done"] is False, "Step was toggled by user B — isolation breach!"

    def test_list_projects_does_not_leak_other_users(self, two_users):
        _, _, _, token_b, _, _ = two_users
        r = requests.get(f"{API}/projects", headers=auth(token_b))
        assert r.status_code == 200
        projects = r.json()
        # User B has no projects — must be empty
        assert len(projects) == 0, f"User B sees user A's projects: {projects}"


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    db.users.delete_many({"email": {"$regex": "TEST\\.ISO"}})
