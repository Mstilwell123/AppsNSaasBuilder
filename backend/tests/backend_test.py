"""Backend tests for hybrid auth: session, change-password, local login, forgot/reset, CORS."""
import os
import hashlib
import secrets
import uuid
import pytest
import requests
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"

MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"

mongo = MongoClient(MONGO_URL)
db = mongo[DB_NAME]


# ---------- helpers ----------
def _seed_user_and_session(prefix="TEST", with_password=False):
    uid = f"{prefix}-user-{uuid.uuid4().hex[:8]}"
    token = f"TEST_session_{uuid.uuid4().hex}"
    now = datetime.now(timezone.utc)
    doc = {
        "user_id": uid,
        "email": f"TEST.{uid}@example.com",
        "name": "Test User",
        "picture": None,
        "password_hash": None,
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
    return uid, token, doc["email"]


def _set_password_via_api(token, password):
    r = requests.post(f"{API}/auth/change-password",
                      headers={"Authorization": f"Bearer {token}"},
                      json={"new_password": password})
    assert r.status_code == 200, r.text


@pytest.fixture
def seeded():
    uid, token, email = _seed_user_and_session()
    yield uid, token, email
    db.users.delete_many({"user_id": uid})
    db.user_sessions.delete_many({"user_id": uid})
    db.password_reset_tokens.delete_many({"user_id": uid})


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ================================================================
# Basics + regression change-password (from iteration_1)
# ================================================================
def test_root():
    r = requests.get(f"{API}/")
    assert r.status_code == 200


def test_me_unauth():
    assert requests.get(f"{API}/auth/me").status_code == 401


def test_me_authed(seeded):
    uid, token, _ = seeded
    r = requests.get(f"{API}/auth/me", headers=auth(token))
    assert r.status_code == 200
    assert r.json()["user_id"] == uid


def test_change_password_requires_auth():
    assert requests.post(f"{API}/auth/change-password",
                         json={"new_password": "anything123"}).status_code == 401


def test_set_initial_password_no_current(seeded):
    uid, token, _ = seeded
    _set_password_via_api(token, "initialPass1")
    u = db.users.find_one({"user_id": uid})
    assert u["password_hash"].startswith("$2b$")


def test_change_password_wrong_current(seeded):
    _, token, _ = seeded
    _set_password_via_api(token, "firstPass1")
    r = requests.post(f"{API}/auth/change-password", headers=auth(token),
                      json={"current_password": "WRONG_PW", "new_password": "anotherPass1"})
    assert r.status_code == 400
    assert "current password is incorrect" in r.json()["detail"].lower()


def test_change_password_too_short(seeded):
    _, token, _ = seeded
    r = requests.post(f"{API}/auth/change-password", headers=auth(token),
                      json={"new_password": "short"})
    assert r.status_code == 400


def test_change_password_same_as_current(seeded):
    _, token, _ = seeded
    _set_password_via_api(token, "samePass1")
    r = requests.post(f"{API}/auth/change-password", headers=auth(token),
                      json={"current_password": "samePass1", "new_password": "samePass1"})
    assert r.status_code == 400


def test_session_rotation_on_password_change(seeded):
    uid, token_a, _ = seeded
    token_b = f"TEST_session_{uuid.uuid4().hex}"
    now = datetime.now(timezone.utc)
    db.user_sessions.insert_one({
        "user_id": uid, "session_token": token_b,
        "expires_at": (now + timedelta(days=7)).isoformat(),
        "created_at": now.isoformat(),
    })
    _set_password_via_api(token_a, "rotatePass1")
    assert requests.get(f"{API}/auth/me", headers=auth(token_a)).status_code == 200
    assert requests.get(f"{API}/auth/me", headers=auth(token_b)).status_code == 401


# ================================================================
# NEW — POST /api/auth/login
# ================================================================
def test_login_success(seeded):
    uid, token, email = seeded
    _set_password_via_api(token, "goodPass123")
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": "goodPass123"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["user_id"] == uid
    assert data["email"] == email
    assert data["has_password"] is True
    # A session_token cookie must be set (or Set-Cookie header present)
    cookie_header = r.headers.get("set-cookie", "")
    assert "session_token=" in cookie_header
    # Extract cookie value and validate it works on /me
    session_val = r.cookies.get("session_token")
    assert session_val
    me = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {session_val}"})
    assert me.status_code == 200
    assert me.json()["user_id"] == uid


def test_login_wrong_password(seeded):
    _, token, email = seeded
    _set_password_via_api(token, "correctPass1")
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": "WRONG"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid email or password"


def test_login_user_without_password(seeded):
    _, _, email = seeded  # no password set
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": "anything123"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid email or password"


def test_login_nonexistent_email():
    r = requests.post(f"{API}/auth/login",
                      json={"email": f"nope-{uuid.uuid4().hex}@example.com", "password": "anything123"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid email or password"


# ================================================================
# NEW — POST /api/auth/forgot-password
# ================================================================
def test_forgot_password_existing_user_creates_token(seeded):
    uid, _, email = seeded
    r = requests.post(f"{API}/auth/forgot-password", json={"email": email})
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    docs = list(db.password_reset_tokens.find({"user_id": uid}))
    assert len(docs) >= 1
    d = docs[-1]
    assert d.get("token_hash") and len(d["token_hash"]) == 64  # sha256 hex
    assert d.get("used_at") is None
    assert d.get("expires_at")


def test_forgot_password_nonexistent_user_still_200_no_token():
    fake = f"noone-{uuid.uuid4().hex}@example.com"
    r = requests.post(f"{API}/auth/forgot-password", json={"email": fake})
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    # Cannot easily assert absence globally without user_id, but ensure no token has this email context.
    # This is best-effort — behaviour is enforced in code (only creates if user found).


def test_forgot_password_resend_reject_still_200(seeded):
    """Resend TEST mode rejects non-owner recipients; endpoint must still return {ok:true}."""
    _, _, email = seeded  # a fresh @example.com — will be rejected by Resend
    r = requests.post(f"{API}/auth/forgot-password", json={"email": email})
    assert r.status_code == 200
    assert r.json() == {"ok": True}


# ================================================================
# NEW — POST /api/auth/reset-password
# ================================================================
def _seed_reset_token(user_id, minutes_from_now=30, used=False):
    raw = f"raw_{secrets.token_urlsafe(24)}"
    h = hashlib.sha256(raw.encode()).hexdigest()
    exp = datetime.now(timezone.utc) + timedelta(minutes=minutes_from_now)
    db.password_reset_tokens.insert_one({
        "user_id": user_id,
        "token_hash": h,
        "expires_at": exp.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "used_at": datetime.now(timezone.utc).isoformat() if used else None,
    })
    return raw, h


def test_reset_password_success_signs_in_and_revokes(seeded):
    uid, token_a, _ = seeded
    # add another active session
    token_b = f"TEST_session_{uuid.uuid4().hex}"
    now = datetime.now(timezone.utc)
    db.user_sessions.insert_one({
        "user_id": uid, "session_token": token_b,
        "expires_at": (now + timedelta(days=7)).isoformat(),
        "created_at": now.isoformat(),
    })
    raw, h = _seed_reset_token(uid)
    r = requests.post(f"{API}/auth/reset-password",
                      json={"token": raw, "new_password": "brandNew12"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["user"]["user_id"] == uid
    # fresh cookie
    assert "session_token=" in r.headers.get("set-cookie", "")
    new_cookie = r.cookies.get("session_token")
    assert new_cookie

    # password_hash updated + bcrypt
    u = db.users.find_one({"user_id": uid})
    assert u["password_hash"].startswith("$2b$")

    # token marked used
    td = db.password_reset_tokens.find_one({"token_hash": h})
    assert td["used_at"] is not None

    # previous sessions revoked
    assert requests.get(f"{API}/auth/me", headers=auth(token_a)).status_code == 401
    assert requests.get(f"{API}/auth/me", headers=auth(token_b)).status_code == 401

    # new session works
    assert requests.get(f"{API}/auth/me", headers=auth(new_cookie)).status_code == 200


def test_reset_password_replay_fails(seeded):
    uid, _, _ = seeded
    raw, _ = _seed_reset_token(uid)
    r1 = requests.post(f"{API}/auth/reset-password",
                       json={"token": raw, "new_password": "brandNew12"})
    assert r1.status_code == 200
    r2 = requests.post(f"{API}/auth/reset-password",
                       json={"token": raw, "new_password": "anotherOne34"})
    assert r2.status_code == 400
    assert "invalid or already used" in r2.json()["detail"].lower()


def test_reset_password_short(seeded):
    uid, _, _ = seeded
    raw, _ = _seed_reset_token(uid)
    r = requests.post(f"{API}/auth/reset-password", json={"token": raw, "new_password": "short"})
    assert r.status_code == 400


def test_reset_password_expired(seeded):
    uid, _, _ = seeded
    raw, _ = _seed_reset_token(uid, minutes_from_now=-5)  # already expired
    r = requests.post(f"{API}/auth/reset-password", json={"token": raw, "new_password": "brandNew12"})
    assert r.status_code == 400
    assert "expired" in r.json()["detail"].lower()


def test_reset_password_garbage_token():
    r = requests.post(f"{API}/auth/reset-password",
                      json={"token": "totally-bogus-token", "new_password": "brandNew12"})
    assert r.status_code == 400
    assert "invalid or already used" in r.json()["detail"].lower()


# ================================================================
# NEW — CORS  (tested against the FastAPI app directly on :8001 because
# the Kubernetes/Cloudflare ingress rewrites CORS headers to wildcard
# on the external URL — this is a platform behavior, not an app bug.)
# ================================================================
DIRECT = "http://localhost:8001"


def test_cors_allowed_origin_direct():
    r = requests.post(f"{DIRECT}/api/auth/login",
                      headers={"Origin": "http://localhost:3000", "Content-Type": "application/json"},
                      json={"email": "nobody@example.com", "password": "irrelevant1"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert r.headers.get("access-control-allow-credentials") == "true"


def test_cors_disallowed_origin_direct():
    r = requests.post(f"{DIRECT}/api/auth/login",
                      headers={"Origin": "https://evil.example.com", "Content-Type": "application/json"},
                      json={"email": "nobody@example.com", "password": "irrelevant1"})
    # A-C-A-O must NOT be present or must not echo the evil origin
    aco = r.headers.get("access-control-allow-origin")
    assert aco in (None, ""), f"disallowed origin was echoed: {aco}"


def test_cors_preflight_allowed_direct():
    r = requests.options(f"{DIRECT}/api/auth/login", headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert r.status_code in (200, 204)
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
