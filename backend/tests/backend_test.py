"""Backend tests for hybrid auth + change-password feature."""
import os
import time
import uuid
import pytest
import requests
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
if not BASE_URL:
    # fall back to reading frontend .env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"

MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"

mongo = MongoClient(MONGO_URL)
db = mongo[DB_NAME]


def _seed_user_and_session(prefix="TEST"):
    uid = f"{prefix}-user-{uuid.uuid4().hex[:8]}"
    token = f"TEST_session_{uuid.uuid4().hex}"
    now = datetime.now(timezone.utc)
    db.users.insert_one({
        "user_id": uid,
        "email": f"{prefix}.{uid}@example.com",
        "name": "Test User",
        "picture": None,
        "password_hash": None,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    })
    db.user_sessions.insert_one({
        "user_id": uid,
        "session_token": token,
        "expires_at": (now + timedelta(days=7)).isoformat(),
        "created_at": now.isoformat(),
    })
    return uid, token


@pytest.fixture
def seeded():
    uid, token = _seed_user_and_session()
    yield uid, token
    db.users.delete_many({"user_id": uid})
    db.user_sessions.delete_many({"user_id": uid})


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- basics ----------
def test_root():
    r = requests.get(f"{API}/")
    assert r.status_code == 200


def test_me_unauth():
    r = requests.get(f"{API}/auth/me")
    assert r.status_code == 401


def test_me_authed(seeded):
    uid, token = seeded
    r = requests.get(f"{API}/auth/me", headers=auth(token))
    assert r.status_code == 200
    data = r.json()
    assert data["user_id"] == uid
    assert data["has_password"] is False
    assert "email" in data and "name" in data


# ---------- change password flow ----------
def test_set_initial_password_no_current(seeded):
    uid, token = seeded
    r = requests.post(f"{API}/auth/change-password",
                      headers=auth(token),
                      json={"new_password": "initialPass1"})
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True

    # verify in mongo
    u = db.users.find_one({"user_id": uid})
    assert u["password_hash"].startswith("$2b$")

    # /me now reports has_password true
    me = requests.get(f"{API}/auth/me", headers=auth(token)).json()
    assert me["has_password"] is True


def test_change_password_wrong_current(seeded):
    uid, token = seeded
    requests.post(f"{API}/auth/change-password", headers=auth(token),
                  json={"new_password": "firstPass1"})
    r = requests.post(f"{API}/auth/change-password", headers=auth(token),
                      json={"current_password": "WRONG_PW", "new_password": "anotherPass1"})
    assert r.status_code == 400
    assert "current password is incorrect" in r.json()["detail"].lower()


def test_change_password_too_short(seeded):
    uid, token = seeded
    r = requests.post(f"{API}/auth/change-password", headers=auth(token),
                      json={"new_password": "short"})
    assert r.status_code == 400
    assert "8" in r.json()["detail"]


def test_change_password_same_as_current(seeded):
    uid, token = seeded
    pw = "samePass1"
    requests.post(f"{API}/auth/change-password", headers=auth(token),
                  json={"new_password": pw})
    r = requests.post(f"{API}/auth/change-password", headers=auth(token),
                      json={"current_password": pw, "new_password": pw})
    assert r.status_code == 400
    assert "different" in r.json()["detail"].lower()


def test_session_rotation_on_password_change(seeded):
    """Session A changes password → A still valid, B revoked."""
    uid, token_a = seeded
    # add second session for same user
    token_b = f"TEST_session_{uuid.uuid4().hex}"
    now = datetime.now(timezone.utc)
    db.user_sessions.insert_one({
        "user_id": uid,
        "session_token": token_b,
        "expires_at": (now + timedelta(days=7)).isoformat(),
        "created_at": now.isoformat(),
    })

    # both work initially
    assert requests.get(f"{API}/auth/me", headers=auth(token_a)).status_code == 200
    assert requests.get(f"{API}/auth/me", headers=auth(token_b)).status_code == 200

    # A sets initial password
    r = requests.post(f"{API}/auth/change-password", headers=auth(token_a),
                      json={"new_password": "rotatePass1"})
    assert r.status_code == 200

    # A still authenticated
    assert requests.get(f"{API}/auth/me", headers=auth(token_a)).status_code == 200
    # B revoked
    rb = requests.get(f"{API}/auth/me", headers=auth(token_b))
    assert rb.status_code == 401


def test_logout_revokes_session(seeded):
    uid, token = seeded
    assert requests.get(f"{API}/auth/me", headers=auth(token)).status_code == 200
    r = requests.post(f"{API}/auth/logout", headers=auth(token))
    assert r.status_code == 200
    assert requests.get(f"{API}/auth/me", headers=auth(token)).status_code == 401


def test_change_password_requires_auth():
    r = requests.post(f"{API}/auth/change-password", json={"new_password": "anything123"})
    assert r.status_code == 401


def test_change_password_valid_current_and_new(seeded):
    uid, token = seeded
    requests.post(f"{API}/auth/change-password", headers=auth(token),
                  json={"new_password": "firstPass1"})
    r = requests.post(f"{API}/auth/change-password", headers=auth(token),
                      json={"current_password": "firstPass1", "new_password": "secondPass2"})
    assert r.status_code == 200
    # session still works
    assert requests.get(f"{API}/auth/me", headers=auth(token)).status_code == 200
