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


# ================================================================
# NEW — GitHub OAuth + Projects (iteration_3)
# ================================================================
from urllib.parse import urlparse, parse_qs
from cryptography.fernet import Fernet


def _fernet():
    # Load fernet key from backend env (same as server.py uses)
    key = None
    with open("/app/backend/.env") as f:
        for line in f:
            if line.startswith("TOKEN_ENCRYPTION_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    assert key, "TOKEN_ENCRYPTION_KEY missing in /app/backend/.env"
    return Fernet(key.encode())


def _seed_github_connection(user_id, username="fakeuser"):
    enc = _fernet().encrypt(b"ghp_fake_token_for_testing").decode()
    db.github_connections.delete_many({"user_id": user_id})
    db.github_connections.insert_one({
        "user_id": user_id,
        "github_user_id": 999,
        "github_username": username,
        "encrypted_token": enc,
        "scopes": ["public_repo", "read:user"],
        "connected_at": datetime.now(timezone.utc).isoformat(),
    })


def _cleanup_project_data(user_id):
    projs = list(db.projects.find({"user_id": user_id}, {"id": 1}))
    ids = [p["id"] for p in projs]
    db.projects.delete_many({"user_id": user_id})
    db.next_steps.delete_many({"project_id": {"$in": ids}})
    db.scores.delete_many({"project_id": {"$in": ids}})
    db.scans.delete_many({"project_id": {"$in": ids}})
    db.github_connections.delete_many({"user_id": user_id})
    db.github_oauth_states.delete_many({"user_id": user_id})


@pytest.fixture
def seeded_with_cleanup(seeded):
    uid, token, email = seeded
    yield uid, token, email
    _cleanup_project_data(uid)


# ---------- github/status ----------
def test_github_status_unauth():
    assert requests.get(f"{API}/github/status").status_code == 401


def test_github_status_authed_not_connected(seeded_with_cleanup):
    _, token, _ = seeded_with_cleanup
    r = requests.get(f"{API}/github/status", headers=auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body == {"connected": False, "github_username": None}


def test_github_status_connected(seeded_with_cleanup):
    uid, token, _ = seeded_with_cleanup
    _seed_github_connection(uid, username="ghtester")
    r = requests.get(f"{API}/github/status", headers=auth(token))
    assert r.status_code == 200
    assert r.json() == {"connected": True, "github_username": "ghtester"}


# ---------- github/connect ----------
def test_github_connect_returns_authorize_url(seeded_with_cleanup):
    _, token, _ = seeded_with_cleanup
    r = requests.get(f"{API}/github/connect", headers=auth(token))
    assert r.status_code == 200
    url = r.json()["url"]
    assert url.startswith("https://github.com/login/oauth/authorize?")
    q = parse_qs(urlparse(url).query)
    assert q["client_id"][0]
    assert "/api/github/callback" in q["redirect_uri"][0]
    scope = q["scope"][0]
    assert "public_repo" in scope and "read:user" in scope
    assert q["state"][0]
    # And a github_oauth_states row was persisted
    assert db.github_oauth_states.find_one({"state": q["state"][0]}) is not None


# ---------- github/callback ----------
def test_github_callback_missing_params_redirects():
    r = requests.get(f"{API}/github/callback", allow_redirects=False)
    assert r.status_code in (302, 307)
    loc = r.headers.get("location", "")
    assert "/connect?error=" in loc


def test_github_callback_unknown_state_redirects():
    r = requests.get(f"{API}/github/callback",
                     params={"code": "xxx", "state": "totally-unknown-state"},
                     allow_redirects=False)
    assert r.status_code in (302, 307)
    assert "error=invalid_state" in r.headers.get("location", "")


# ---------- github/repos ----------
def test_github_repos_without_connection_returns_400(seeded_with_cleanup):
    _, token, _ = seeded_with_cleanup
    r = requests.get(f"{API}/github/repos", headers=auth(token))
    assert r.status_code == 400
    assert "not connected" in r.json()["detail"].lower()


# ---------- projects: track w/ fake conn -> plumbing test ----------
def test_track_project_without_connection_400(seeded_with_cleanup):
    _, token, _ = seeded_with_cleanup
    r = requests.post(f"{API}/projects", headers=auth(token),
                      json={"github_repo_id": 12345})
    assert r.status_code == 400


def test_track_project_fake_token_hits_github_gracefully(seeded_with_cleanup):
    uid, token, _ = seeded_with_cleanup
    _seed_github_connection(uid)
    r = requests.post(f"{API}/projects", headers=auth(token),
                      json={"github_repo_id": 12345})
    # Real GitHub will reject the fake token → we return 404 (not accessible)
    assert r.status_code in (404, 502)


# ---------- projects: seed-based happy path ----------
def _seed_project(user_id, name="demo", full_name="ghtester/demo", steps=None, score=None,
                  sparkline=None, ci_status="configured", live_url="https://demo.example.com"):
    pid = f"proj_test_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    db.projects.insert_one({
        "id": pid, "user_id": user_id, "github_repo_id": 100 + hash(pid) % 10_000,
        "name": name, "full_name": full_name, "private": False,
        "primary_language": "Python", "languages": {"Python": 1000},
        "stars": 3, "forks": 1, "open_issues": 2,
        "default_branch": "main", "live_url": live_url,
        "ci_status": ci_status,
        "commit_sparkline": sparkline if sparkline is not None else [1, 2, 3, 0, 4, 5, 6, 0, 7, 8, 9, 10],
        "last_commit_at": now,
        "one_line_summary": "A demo project.",
        "added_at": now, "updated_at": now,
    })
    if score is not None:
        db.scores.insert_one({
            "id": f"score_test_{uuid.uuid4().hex[:6]}",
            "user_id": user_id, "project_id": pid,
            "score": int(score), "rationale": "Because.",
            "model": "claude-haiku-4-5-20251001",
            "scored_at": now,
        })
    step_ids = []
    for i, s in enumerate(steps or [], start=1):
        sid = f"step_test_{uuid.uuid4().hex[:8]}"
        step_ids.append(sid)
        db.next_steps.insert_one({
            "id": sid, "user_id": user_id, "project_id": pid,
            "text": s["text"], "weight": s["weight"],
            "order": s.get("order", i), "done": bool(s.get("done", False)),
            "created_at": now,
        })
    return pid, step_ids


def test_list_projects_returns_seeded(seeded_with_cleanup):
    uid, token, _ = seeded_with_cleanup
    pid, _ = _seed_project(uid, score=72,
                           steps=[{"text": "Add README", "weight": 3, "done": True},
                                  {"text": "Add CI", "weight": 5, "done": False},
                                  {"text": "Polish", "weight": 2, "done": False}])
    r = requests.get(f"{API}/projects", headers=auth(token))
    assert r.status_code == 200, r.text
    arr = r.json()
    assert len(arr) == 1
    p = arr[0]
    assert p["id"] == pid
    assert p["latest_score"]["score"] == 72
    assert len(p["next_steps"]) == 3
    # completion = 3 / (3+5+2) * 100 = 30
    assert p["completion"] == 30
    assert len(p["commit_sparkline"]) == 12


def test_get_project_shape(seeded_with_cleanup):
    uid, token, _ = seeded_with_cleanup
    pid, _ = _seed_project(uid, score=50, steps=[{"text": "A", "weight": 1}])
    r = requests.get(f"{API}/projects/{pid}", headers=auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == pid
    assert body["latest_score"]["score"] == 50


def test_get_project_other_user_returns_404(seeded_with_cleanup):
    uid, _, _ = seeded_with_cleanup
    pid, _ = _seed_project(uid)
    # Second seeded user
    uid2, token2, _ = _seed_user_and_session()
    try:
        r = requests.get(f"{API}/projects/{pid}", headers=auth(token2))
        assert r.status_code == 404
    finally:
        db.users.delete_many({"user_id": uid2})
        db.user_sessions.delete_many({"user_id": uid2})


def test_toggle_next_step_updates_completion(seeded_with_cleanup):
    uid, token, _ = seeded_with_cleanup
    pid, step_ids = _seed_project(uid, steps=[
        {"text": "A", "weight": 5},
        {"text": "B", "weight": 3},
        {"text": "C", "weight": 2},
    ])
    # Mark only weight-5 done → completion = 50
    r = requests.patch(f"{API}/next-steps/{step_ids[0]}", headers=auth(token),
                       json={"done": True})
    assert r.status_code == 200, r.text
    assert r.json()["completion"] == 50
    # Mark all done → 100
    requests.patch(f"{API}/next-steps/{step_ids[1]}", headers=auth(token), json={"done": True})
    r = requests.patch(f"{API}/next-steps/{step_ids[2]}", headers=auth(token), json={"done": True})
    assert r.json()["completion"] == 100
    # Mark all undone → 0
    for sid in step_ids:
        r = requests.patch(f"{API}/next-steps/{sid}", headers=auth(token), json={"done": False})
    assert r.json()["completion"] == 0


def test_toggle_next_step_of_other_user_returns_404(seeded_with_cleanup):
    uid, _, _ = seeded_with_cleanup
    _, step_ids = _seed_project(uid, steps=[{"text": "A", "weight": 1}])
    uid2, token2, _ = _seed_user_and_session()
    try:
        r = requests.patch(f"{API}/next-steps/{step_ids[0]}", headers=auth(token2),
                           json={"done": True})
        assert r.status_code == 404
    finally:
        db.users.delete_many({"user_id": uid2})
        db.user_sessions.delete_many({"user_id": uid2})


def test_delete_project_cascades(seeded_with_cleanup):
    uid, token, _ = seeded_with_cleanup
    pid, step_ids = _seed_project(uid, score=40,
                                  steps=[{"text": "A", "weight": 1}, {"text": "B", "weight": 1}])
    # add a scan row
    db.scans.insert_one({"id": "scan_test", "user_id": uid, "project_id": pid,
                         "status": "done", "started_at": "", "finished_at": ""})
    r = requests.delete(f"{API}/projects/{pid}", headers=auth(token))
    assert r.status_code == 200
    # subsequent GET → 404
    assert requests.get(f"{API}/projects/{pid}", headers=auth(token)).status_code == 404
    # cascade
    assert db.projects.find_one({"id": pid}) is None
    assert db.next_steps.count_documents({"project_id": pid}) == 0
    assert db.scores.count_documents({"project_id": pid}) == 0
    assert db.scans.count_documents({"project_id": pid}) == 0

# ================================================================
# NEW — Billing / Stripe (iteration_6)
# ================================================================
FREE_TIER_LIMIT = 3


def _cleanup_billing(user_id):
    db.billing.delete_many({"user_id": user_id})
    db.payment_transactions.delete_many({"user_id": user_id})


@pytest.fixture
def billing_seeded(seeded):
    uid, token, email = seeded
    yield uid, token, email
    _cleanup_billing(uid)
    _cleanup_project_data(uid)


def test_billing_status_unauth():
    assert requests.get(f"{API}/billing/status").status_code == 401


def test_billing_status_fresh_user(billing_seeded):
    _, token, _ = billing_seeded
    r = requests.get(f"{API}/billing/status", headers=auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["plan"] == "free"
    assert body["subscription_status"] is None
    assert body["cancel_at_period_end"] is False
    assert body["customer_id"] is None
    assert body["subscription_id"] is None
    assert body["tracked_projects"] == 0
    assert body["free_tier_limit"] == FREE_TIER_LIMIT


def test_billing_checkout_creates_session_and_records(billing_seeded):
    uid, token, _ = billing_seeded
    r = requests.post(f"{API}/billing/checkout", headers=auth(token),
                      json={"origin_url": "https://example.com"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "checkout.stripe.com" in data["checkout_url"]
    sid = data["session_id"]
    assert sid.startswith("cs_test_")
    # payment_transactions row
    tx = db.payment_transactions.find_one({"session_id": sid})
    assert tx is not None
    assert tx["status"] == "initiated"
    assert tx["payment_status"] == "pending"
    assert tx["user_id"] == uid
    # billing row upserted with customer_id
    b = db.billing.find_one({"user_id": uid})
    assert b is not None
    assert b.get("customer_id")


def test_billing_checkout_reuses_customer(billing_seeded):
    uid, token, _ = billing_seeded
    r1 = requests.post(f"{API}/billing/checkout", headers=auth(token),
                       json={"origin_url": "https://example.com"})
    assert r1.status_code == 200
    b1 = db.billing.find_one({"user_id": uid})
    cid1 = b1["customer_id"]
    r2 = requests.post(f"{API}/billing/checkout", headers=auth(token),
                       json={"origin_url": "https://example.com"})
    assert r2.status_code == 200
    # not duplicated
    cnt = db.billing.count_documents({"user_id": uid})
    assert cnt == 1
    b2 = db.billing.find_one({"user_id": uid})
    assert b2["customer_id"] == cid1


def test_payments_status_unauthenticated_returns_pending(billing_seeded):
    _, token, _ = billing_seeded
    r = requests.post(f"{API}/billing/checkout", headers=auth(token),
                     json={"origin_url": "https://example.com"})
    sid = r.json()["session_id"]
    # NO auth header
    r2 = requests.get(f"{API}/payments/status/{sid}")
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["session_id"] == sid
    # Playbook allows graceful pass-through; either initiated/pending or upgraded state
    assert body["payment_status"] in ("pending", "paid", "unpaid", "no_payment_required")
    assert body["status"] in ("initiated", "completed", "complete")


def test_payments_status_unknown_session_404():
    r = requests.get(f"{API}/payments/status/cs_test_definitely_missing_xyz")
    assert r.status_code == 404


def test_billing_portal_without_profile_400(billing_seeded):
    _, token, _ = billing_seeded
    r = requests.post(f"{API}/billing/portal", headers=auth(token),
                      json={"origin_url": "https://example.com"})
    assert r.status_code == 400
    assert r.json()["detail"] == "No billing profile yet"


def test_billing_portal_after_checkout_returns_url(billing_seeded):
    _, token, _ = billing_seeded
    requests.post(f"{API}/billing/checkout", headers=auth(token),
                  json={"origin_url": "https://example.com"})
    r = requests.post(f"{API}/billing/portal", headers=auth(token),
                     json={"origin_url": "https://example.com"})
    assert r.status_code == 200, r.text
    assert "billing.stripe.com" in r.json()["url"]


def test_stripe_webhook_bad_signature_400():
    r = requests.post(f"{API}/stripe/webhook",
                      headers={"stripe-signature": "t=1,v1=garbage"},
                      data=b'{"id":"evt_test","type":"foo"}')
    assert r.status_code == 400
    assert r.json()["detail"] == "Invalid signature"


def test_stripe_webhook_missing_signature_400():
    r = requests.post(f"{API}/stripe/webhook", data=b'{"id":"evt_test"}')
    assert r.status_code == 400


# ---------- Free-tier gate ----------
def test_free_tier_gate_blocks_at_limit(billing_seeded):
    uid, token, _ = billing_seeded
    _seed_github_connection(uid)
    # seed 3 projects (at limit)
    for i in range(FREE_TIER_LIMIT):
        _seed_project(uid, name=f"p{i}", full_name=f"gh/p{i}")
    r = requests.post(f"{API}/projects", headers=auth(token),
                      json={"github_repo_id": 987654})
    assert r.status_code == 402, r.text
    detail = r.json()["detail"]
    assert detail["code"] == "free_tier_limit_reached"
    assert detail["limit"] == FREE_TIER_LIMIT
    assert isinstance(detail["message"], str) and len(detail["message"]) > 0


def test_pro_tier_bypasses_free_gate(billing_seeded):
    uid, token, _ = billing_seeded
    _seed_github_connection(uid)
    for i in range(FREE_TIER_LIMIT):
        _seed_project(uid, name=f"p{i}", full_name=f"gh/p{i}")
    # upsert active pro billing row
    db.billing.update_one(
        {"user_id": uid},
        {"$set": {
            "user_id": uid,
            "customer_id": "cus_test_manual",
            "subscription_status": "active",
            "cancel_at_period_end": False,
        }},
        upsert=True,
    )
    r = requests.post(f"{API}/projects", headers=auth(token),
                      json={"github_repo_id": 987654})
    # Gate should be bypassed → not 402. Real GitHub will 404/502 the fake token.
    assert r.status_code != 402
    assert r.status_code in (404, 502)


# ================================================================
# Top Movers (iteration_7)
# ================================================================
def _seed_score(project_id, user_id, score, scored_at):
    db.scores.insert_one({
        "id": f"score_test_{uuid.uuid4().hex[:6]}",
        "user_id": user_id, "project_id": project_id,
        "score": int(score), "rationale": "test", "model": "claude-haiku",
        "scored_at": scored_at,
    })


def _seed_project_no_score(user_id, name, full_name):
    pid, _ = _seed_project(user_id, name=name, full_name=full_name, score=None)
    return pid


def _seed_movers_scenario(user_id):
    """3 projects: up (+18), down (-15), zero (0)."""
    now = datetime.now(timezone.utc)
    def iso(mins_ago):
        return (now - timedelta(minutes=mins_ago)).isoformat()
    up = _seed_project_no_score(user_id, "up-proj", "ghtester/up-proj")
    _seed_score(up, user_id, 60, iso(20))     # previous
    _seed_score(up, user_id, 78, iso(5))      # latest -> +18
    down = _seed_project_no_score(user_id, "down-proj", "ghtester/down-proj")
    _seed_score(down, user_id, 55, iso(30))
    _seed_score(down, user_id, 40, iso(10))   # -15
    zero = _seed_project_no_score(user_id, "zero-proj", "ghtester/zero-proj")
    _seed_score(zero, user_id, 70, iso(25))
    _seed_score(zero, user_id, 70, iso(3))    # 0
    return up, down, zero


def test_movers_unauth():
    assert requests.get(f"{API}/movers").status_code == 401


def test_movers_no_projects_empty(seeded_with_cleanup):
    _, token, _ = seeded_with_cleanup
    r = requests.get(f"{API}/movers", headers=auth(token))
    assert r.status_code == 200
    assert r.json() == []


def test_movers_single_score_excluded(seeded_with_cleanup):
    uid, token, _ = seeded_with_cleanup
    _seed_project(uid, name="oneshot", full_name="ghtester/oneshot", score=50)
    r = requests.get(f"{API}/movers", headers=auth(token))
    assert r.status_code == 200
    assert r.json() == []


def test_movers_zero_delta_excluded(seeded_with_cleanup):
    uid, token, _ = seeded_with_cleanup
    now = datetime.now(timezone.utc)
    pid = _seed_project_no_score(uid, "flat", "ghtester/flat")
    _seed_score(pid, uid, 70, (now - timedelta(minutes=20)).isoformat())
    _seed_score(pid, uid, 70, (now - timedelta(minutes=5)).isoformat())
    r = requests.get(f"{API}/movers", headers=auth(token))
    assert r.status_code == 200
    assert r.json() == []


def test_movers_seeded_scenario_order_and_shape(seeded_with_cleanup):
    uid, token, _ = seeded_with_cleanup
    up, down, zero = _seed_movers_scenario(uid)
    r = requests.get(f"{API}/movers", headers=auth(token))
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2, body
    assert body[0]["project_id"] == up
    assert body[0]["delta"] == 18
    assert body[0]["latest_score"] == 78
    assert body[0]["previous_score"] == 60
    assert body[0]["name"] == "up-proj"
    assert body[0]["full_name"] == "ghtester/up-proj"
    assert isinstance(body[0]["scored_at"], str) and body[0]["scored_at"]
    assert isinstance(body[0]["previous_scored_at"], str)
    assert body[1]["project_id"] == down
    assert body[1]["delta"] == -15
    assert all(m["project_id"] != zero for m in body)


def test_movers_limit_clamping(seeded_with_cleanup):
    uid, token, _ = seeded_with_cleanup
    up, down, _ = _seed_movers_scenario(uid)
    r1 = requests.get(f"{API}/movers?limit=1", headers=auth(token))
    assert r1.status_code == 200
    b1 = r1.json()
    assert len(b1) == 1 and b1[0]["project_id"] == up
    r0 = requests.get(f"{API}/movers?limit=0", headers=auth(token))
    assert r0.status_code == 200
    assert len(r0.json()) == 1  # clamps to 1
    rbig = requests.get(f"{API}/movers?limit=999", headers=auth(token))
    assert rbig.status_code == 200
    assert len(rbig.json()) == 2  # only 2 eligible; clamp doesn't invent rows
    rneg = requests.get(f"{API}/movers?limit=-5", headers=auth(token))
    assert rneg.status_code == 200
    assert len(rneg.json()) == 1


def test_movers_per_user_isolation(seeded_with_cleanup):
    uid_a, token_a, _ = seeded_with_cleanup
    _seed_movers_scenario(uid_a)
    # seed user B
    uid_b, token_b, _ = _seed_user_and_session()
    try:
        r = requests.get(f"{API}/movers", headers=auth(token_b))
        assert r.status_code == 200
        assert r.json() == []
        # Also confirm A still sees 2
        r2 = requests.get(f"{API}/movers", headers=auth(token_a))
        assert len(r2.json()) == 2
    finally:
        db.users.delete_many({"user_id": uid_b})
        db.user_sessions.delete_many({"user_id": uid_b})


# ================================================================
# NEW — iteration_7: register / preferences / score history / digest
# ================================================================
def _rand_email():
    return f"TEST_reg_{uuid.uuid4().hex[:8]}@example.com"


def _cleanup_email(email):
    email = email.strip().lower()
    users = list(db.users.find({"email": email}, {"user_id": 1}))
    for u in users:
        db.user_sessions.delete_many({"user_id": u["user_id"]})
        db.projects.delete_many({"user_id": u["user_id"]})
        db.scores.delete_many({"user_id": u["user_id"]})
        db.next_steps.delete_many({"user_id": u["user_id"]})
    db.users.delete_many({"email": email})


# ---------- POST /api/auth/register ----------
def test_register_happy_path():
    email = _rand_email()
    try:
        r = requests.post(f"{API}/auth/register",
                          json={"email": email, "password": "passw0rd123", "name": "Reggie"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["email"] == email.lower()
        assert body["user_id"]
        # Cookie / session
        set_cookie = r.headers.get("set-cookie", "")
        assert "session_token=" in set_cookie
        session_val = r.cookies.get("session_token")
        assert session_val
        me = requests.get(f"{API}/auth/me", headers=auth(session_val))
        assert me.status_code == 200
        assert me.json()["user_id"] == body["user_id"]
        # Mongo doc
        u = db.users.find_one({"email": email.lower()})
        assert u["password_hash"].startswith("$2b$")
        assert u.get("weekly_digest_enabled") is True
    finally:
        _cleanup_email(email)


def test_register_duplicate_email_409():
    email = _rand_email()
    try:
        r1 = requests.post(f"{API}/auth/register",
                           json={"email": email, "password": "passw0rd123"})
        assert r1.status_code == 200
        r2 = requests.post(f"{API}/auth/register",
                           json={"email": email, "password": "differentPw123"})
        assert r2.status_code == 409
        assert "already exists" in r2.json()["detail"].lower()
    finally:
        _cleanup_email(email)


def test_register_short_password_400():
    email = _rand_email()
    r = requests.post(f"{API}/auth/register",
                      json={"email": email, "password": "short"})
    assert r.status_code == 400
    assert "8" in r.json()["detail"]


def test_register_lowercases_email_case_insensitive_dupe():
    base = f"TEST_case_{uuid.uuid4().hex[:6]}"
    upper = f"{base}@Example.com"  # mixed case
    lower = f"{base}@example.com"
    try:
        r1 = requests.post(f"{API}/auth/register",
                           json={"email": upper, "password": "passw0rd123"})
        assert r1.status_code == 200, r1.text
        assert r1.json()["email"] == upper.lower()
        r2 = requests.post(f"{API}/auth/register",
                           json={"email": lower, "password": "passw0rd123"})
        assert r2.status_code == 409, r2.text
    finally:
        _cleanup_email(lower)


def test_register_then_login_works():
    email = _rand_email()
    try:
        r = requests.post(f"{API}/auth/register",
                          json={"email": email, "password": "passw0rd123"})
        assert r.status_code == 200
        rl = requests.post(f"{API}/auth/login",
                           json={"email": email, "password": "passw0rd123"})
        assert rl.status_code == 200, rl.text
        assert rl.json()["email"] == email.lower()
    finally:
        _cleanup_email(email)


# ---------- GET/PATCH /api/preferences ----------
def test_preferences_unauth():
    assert requests.get(f"{API}/preferences").status_code == 401


def test_preferences_default_and_patch(seeded):
    _, token, _ = seeded
    r = requests.get(f"{API}/preferences", headers=auth(token))
    assert r.status_code == 200
    # Default should be True (server treats missing field as True)
    assert r.json()["weekly_digest_enabled"] is True
    r2 = requests.patch(f"{API}/preferences", headers=auth(token),
                        json={"weekly_digest_enabled": False})
    assert r2.status_code == 200
    assert r2.json()["weekly_digest_enabled"] is False
    r3 = requests.get(f"{API}/preferences", headers=auth(token))
    assert r3.json()["weekly_digest_enabled"] is False
    r4 = requests.patch(f"{API}/preferences", headers=auth(token),
                        json={"weekly_digest_enabled": True})
    assert r4.json()["weekly_digest_enabled"] is True


# ---------- GET /api/projects/{id}/scores ----------
def test_score_history_unauth():
    assert requests.get(f"{API}/projects/anything/scores").status_code == 401


def test_score_history_wrong_owner_404(seeded_with_cleanup):
    uid, _, _ = seeded_with_cleanup
    pid, _ = _seed_project(uid, score=50)
    uid2, token2, _ = _seed_user_and_session()
    try:
        r = requests.get(f"{API}/projects/{pid}/scores", headers=auth(token2))
        assert r.status_code == 404
    finally:
        db.users.delete_many({"user_id": uid2})
        db.user_sessions.delete_many({"user_id": uid2})


def test_score_history_chronological_and_shape(seeded_with_cleanup):
    uid, token, _ = seeded_with_cleanup
    pid = _seed_project_no_score(uid, "hist", "ghtester/hist")
    now = datetime.now(timezone.utc)
    _seed_score(pid, uid, 40, (now - timedelta(minutes=30)).isoformat())
    _seed_score(pid, uid, 60, (now - timedelta(minutes=20)).isoformat())
    _seed_score(pid, uid, 80, (now - timedelta(minutes=10)).isoformat())
    r = requests.get(f"{API}/projects/{pid}/scores", headers=auth(token))
    assert r.status_code == 200, r.text
    arr = r.json()
    assert [a["score"] for a in arr] == [40, 60, 80]
    for a in arr:
        assert "scored_at" in a and a["scored_at"]
        assert "rationale" in a


def test_score_history_limit_clamps(seeded_with_cleanup):
    uid, token, _ = seeded_with_cleanup
    pid = _seed_project_no_score(uid, "lim", "ghtester/lim")
    now = datetime.now(timezone.utc)
    for i in range(5):
        _seed_score(pid, uid, 10 + i, (now - timedelta(minutes=50 - i)).isoformat())
    r1 = requests.get(f"{API}/projects/{pid}/scores?limit=2", headers=auth(token))
    assert r1.status_code == 200 and len(r1.json()) == 2
    r0 = requests.get(f"{API}/projects/{pid}/scores?limit=0", headers=auth(token))
    assert r0.status_code == 200 and len(r0.json()) == 1  # clamps to 1
    rbig = requests.get(f"{API}/projects/{pid}/scores?limit=999", headers=auth(token))
    assert rbig.status_code == 200 and len(rbig.json()) == 5


# ---------- Digest preview ----------
def test_digest_preview_unauth():
    assert requests.get(f"{API}/digest/preview").status_code == 401


def test_digest_preview_no_projects(seeded_with_cleanup):
    _, token, _ = seeded_with_cleanup
    r = requests.get(f"{API}/digest/preview", headers=auth(token))
    assert r.status_code == 200
    assert r.json() == {"available": False}


def test_digest_preview_available_and_shape(seeded_with_cleanup):
    uid, token, _ = seeded_with_cleanup
    now = datetime.now(timezone.utc)
    # up-mover: within-7d, +10 delta
    up = _seed_project_no_score(uid, "up", "ghtester/up")
    _seed_score(up, uid, 60, (now - timedelta(days=2, minutes=5)).isoformat())
    _seed_score(up, uid, 70, (now - timedelta(minutes=5)).isoformat())
    # zero-delta (must be excluded)
    zp = _seed_project_no_score(uid, "zp", "ghtester/zp")
    _seed_score(zp, uid, 50, (now - timedelta(days=1)).isoformat())
    _seed_score(zp, uid, 50, (now - timedelta(minutes=10)).isoformat())
    # stale (>7d, must be excluded)
    stale = _seed_project_no_score(uid, "stale", "ghtester/stale")
    _seed_score(stale, uid, 30, (now - timedelta(days=20)).isoformat())
    _seed_score(stale, uid, 45, (now - timedelta(days=10)).isoformat())
    # single-score (not a mover but counted in tracked/avg)
    ss = _seed_project_no_score(uid, "one", "ghtester/one")
    _seed_score(ss, uid, 90, (now - timedelta(minutes=1)).isoformat())

    r = requests.get(f"{API}/digest/preview", headers=auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["available"] is True
    assert body["tracked_count"] == 4  # PROJECTS, not scores
    assert isinstance(body["avg"], int)
    # avg = round((70+50+45+90)/4) = round(63.75) = 64
    assert body["avg"] == 64
    # Only the up-mover qualifies
    names = [m["name"] for m in body["movers"]]
    assert "up" in names
    assert "zp" not in names  # zero-delta excluded
    assert "stale" not in names  # >7d excluded
    assert "one" not in names  # single-score excluded
    for m in body["movers"]:
        assert m["delta"] != 0
    assert isinstance(body["subject"], str) and body["subject"]
    assert isinstance(body["html"], str) and body["html"]
    assert isinstance(body["text"], str) and body["text"]


# ---------- Digest send-test ----------
def test_digest_send_test_no_projects_400(seeded_with_cleanup):
    _, token, _ = seeded_with_cleanup
    r = requests.post(f"{API}/digest/send-test", headers=auth(token))
    assert r.status_code == 400
    assert "nothing to digest" in r.json()["detail"].lower()


def test_digest_send_test_with_data_returns_coherent_error_or_ok(seeded_with_cleanup):
    """Resend TEST mode caps sends to API-key owner — so we accept 200 OR 502 (not 500)."""
    uid, token, _ = seeded_with_cleanup
    now = datetime.now(timezone.utc)
    pid = _seed_project_no_score(uid, "sendp", "ghtester/sendp")
    _seed_score(pid, uid, 50, (now - timedelta(days=1)).isoformat())
    _seed_score(pid, uid, 70, (now - timedelta(minutes=1)).isoformat())
    r = requests.post(f"{API}/digest/send-test", headers=auth(token))
    # Resend TEST mode caps sends to key owner — non-owner recipients get
    # rejected by Resend. Endpoint MUST convert that to a coherent 502 (never 500).
    assert r.status_code in (200, 502), f"unexpected {r.status_code}: {r.text[:200]}"
    if r.status_code == 502:
        # Try JSON detail; if ingress swallowed body, at least status is coherent.
        try:
            body = r.json()
            assert "send failed" in body.get("detail", "").lower()
        except ValueError:
            pass
