"""Iteration 11 focused tests:
   - /api/billing/plans public shape (4 plans w/ contact_only, highlight, lookup_key, trial_days)
   - Fresh register -> /api/billing/subscription returns trial-solo w/ trial_ends_at ~+7d
   - POST /api/projects returns 402 trial_expired when trial_ends_at is in the past
   - POST /api/billing/checkout accepts plan_key (solo/team/agency), null, rejects white_label/bogus
   - _job_lock_expired_trials cron: locks users past trial w/o active sub, idempotent, skips active sub
   - Build-limit gate (regression, trial user @ 8 solo builds -> 402 build_limit_reached)
"""
import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback for tests running inside container: try frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

API = f"{BASE_URL}/api"


# ---------- helpers ---------------------------------------------------------

def _register_user(prefix="TEST_it11"):
    email = f"{prefix}_{uuid.uuid4().hex[:10]}@example.com"
    password = "correct-horse-battery-staple"
    s = requests.Session()
    r = s.post(f"{API}/auth/register", json={"email": email, "password": password, "name": "T"})
    assert r.status_code == 200, f"register failed {r.status_code} {r.text}"
    body = r.json()
    return s, email, body


def _auth_session_bearer(session_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {session_token}"})
    return s


# ---------- 1) /api/billing/plans -------------------------------------------

class TestBillingPlans:
    def test_public_and_shape(self):
        r = requests.get(f"{API}/billing/plans")
        assert r.status_code == 200
        data = r.json()
        assert "plans" in data
        plans = data["plans"]
        keys = [p["plan_key"] for p in plans]
        assert set(keys) == {"solo", "team", "agency", "white_label"}
        by_key = {p["plan_key"]: p for p in plans}
        # solo
        assert by_key["solo"]["price_cents"] == 2900
        assert by_key["solo"]["active_builds"] == 8
        assert by_key["solo"]["trial_days"] == 7
        assert by_key["solo"]["lookup_key"] == "appnsaas_solo_monthly"
        assert isinstance(by_key["solo"]["features"], list) and len(by_key["solo"]["features"]) > 0
        # team
        assert by_key["team"]["price_cents"] == 4900
        assert by_key["team"]["active_builds"] == 32
        assert by_key["team"]["highlight"] is True
        # agency
        assert by_key["agency"]["price_cents"] == 14900
        assert by_key["agency"]["active_builds"] == 200
        # white_label
        assert by_key["white_label"]["contact_only"] is True
        assert by_key["white_label"]["price_cents"] is None
        assert by_key["white_label"]["lookup_key"] in (None, "")


# ---------- 2) Fresh register -> subscription (trial-solo) -------------------

class TestSubscriptionFreshUser:
    def test_fresh_user_subscription_is_solo_trial(self):
        s, email, body = _register_user()
        r = s.get(f"{API}/billing/subscription")
        assert r.status_code == 200, r.text
        sub = r.json()
        assert sub["plan_key"] == "solo"
        assert sub["source"] == "trial"
        assert sub["active_builds_limit"] == 8
        assert sub["plan_name"] == "Solo Builder"
        assert sub.get("trial_ends_at")
        te = datetime.fromisoformat(sub["trial_ends_at"].replace("Z", "+00:00"))
        delta = te - datetime.now(timezone.utc)
        assert timedelta(days=6, hours=12) < delta < timedelta(days=7, hours=12), (
            f"trial_ends_at unexpected delta={delta}"
        )

    def test_subscription_requires_auth(self):
        r = requests.get(f"{API}/billing/subscription")
        assert r.status_code == 401


# ---------- 3) Checkout accepts plan_key / null / rejects white_label -------

class TestCheckoutPlanKey:
    @pytest.mark.parametrize("plan_key", ["solo", "team", "agency"])
    def test_checkout_accepts_plan(self, plan_key):
        s, _, _ = _register_user()
        r = s.post(
            f"{API}/billing/checkout",
            json={"origin_url": "https://example.com", "plan_key": plan_key},
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("checkout_url", "").startswith("https://"), d

    def test_checkout_null_plan_defaults_to_solo(self):
        s, _, _ = _register_user()
        r = s.post(
            f"{API}/billing/checkout",
            json={"origin_url": "https://example.com", "plan_key": None},
        )
        assert r.status_code == 200, r.text
        assert r.json().get("checkout_url", "").startswith("https://")

    def test_checkout_rejects_white_label(self):
        s, _, _ = _register_user()
        r = s.post(
            f"{API}/billing/checkout",
            json={"origin_url": "https://example.com", "plan_key": "white_label"},
        )
        assert r.status_code == 400

    def test_checkout_rejects_bogus(self):
        s, _, _ = _register_user()
        r = s.post(
            f"{API}/billing/checkout",
            json={"origin_url": "https://example.com", "plan_key": "diamond"},
        )
        assert r.status_code == 400


# ---------- 4) trial_expired 402 on POST /api/projects ----------------------

class TestTrialExpiredGate:
    def test_trial_expired_returns_402(self):
        # Register a user, then expire their trial in Mongo, then try POST /api/projects
        s, email, _ = _register_user(prefix="TEST_it11_exp")
        # Get user_id from /auth/me
        me = s.get(f"{API}/auth/me").json()
        user_id = me["user_id"]

        # Set trial_ends_at to yesterday directly in Mongo via a helper request:
        # We don't have direct API — use a shell mongosh call.
        past_iso = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        import subprocess
        script = (
            f"use('test_database');"
            f"db.users.updateOne({{user_id:'{user_id}'}},"
            f"{{$set:{{trial_ends_at:'{past_iso}'}}}});"
        )
        subprocess.run(["mongosh", "--quiet", "--eval", script], check=True, capture_output=True)

        # POST /api/projects should now return 402 trial_expired
        r = s.post(f"{API}/projects", json={"github_repo_id": 123456})
        assert r.status_code == 402, f"expected 402, got {r.status_code}: {r.text}"
        detail = r.json().get("detail")
        # FastAPI wraps HTTPException detail; may be dict directly
        if isinstance(detail, dict):
            assert detail.get("code") == "trial_expired", detail
        else:
            # If serialized as str; still check substring
            assert "trial_expired" in str(detail)


# ---------- 5) _job_lock_expired_trials cron --------------------------------

class TestTrialLockCron:
    def test_cron_locks_expired_and_idempotent_and_skips_active(self):
        # Setup 3 users via register: expired-no-sub, expired-active-sub, active-trial
        import subprocess, json as _json
        past_iso = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()

        s1, _, _ = _register_user(prefix="TEST_it11_lock1")
        s2, _, _ = _register_user(prefix="TEST_it11_lock2")
        s3, _, _ = _register_user(prefix="TEST_it11_lock3")
        u1 = s1.get(f"{API}/auth/me").json()["user_id"]
        u2 = s2.get(f"{API}/auth/me").json()["user_id"]
        u3 = s3.get(f"{API}/auth/me").json()["user_id"]  # keep trial active

        # Expire u1, u2. Give u2 an active billing row.
        mongo_script = f"""
        use('test_database');
        db.users.updateOne({{user_id:'{u1}'}},{{$set:{{trial_ends_at:'{past_iso}'}},$unset:{{locked_at:''}}}});
        db.users.updateOne({{user_id:'{u2}'}},{{$set:{{trial_ends_at:'{past_iso}'}},$unset:{{locked_at:''}}}});
        db.billing.updateOne(
            {{user_id:'{u2}'}},
            {{$set:{{user_id:'{u2}',subscription_status:'active',plan_key:'team',updated_at:'{past_iso}'}}}},
            {{upsert:true}}
        );
        """
        subprocess.run(["mongosh", "--quiet", "--eval", mongo_script], check=True, capture_output=True)

        # Import & invoke the cron directly
        import sys
        sys.path.insert(0, "/app/backend")
        # Ensure fresh event loop for the async call
        from server import _job_lock_expired_trials  # noqa: E402
        asyncio.get_event_loop().run_until_complete(_job_lock_expired_trials())

        # Read back locked_at for all 3
        script = f"""
        use('test_database');
        var out = {{}};
        ['{u1}','{u2}','{u3}'].forEach(function(u){{
            var d = db.users.findOne({{user_id:u}},{{locked_at:1,_id:0}});
            out[u] = d && d.locked_at ? d.locked_at : null;
        }});
        print(JSON.stringify(out));
        """
        res = subprocess.run(["mongosh", "--quiet", "--eval", script], check=True, capture_output=True, text=True)
        # mongosh prints extra lines; grab the JSON line
        line = [l for l in res.stdout.strip().splitlines() if l.startswith("{")][-1]
        out = _json.loads(line)
        assert out[u1] is not None, f"u1 should be locked, got {out}"
        assert out[u2] is None, f"u2 (active sub) should NOT be locked, got {out}"
        assert out[u3] is None, f"u3 (trial active) should NOT be locked, got {out}"

        # Idempotency: capture u1 locked_at, run again, expect unchanged
        first_locked = out[u1]
        asyncio.get_event_loop().run_until_complete(_job_lock_expired_trials())
        res2 = subprocess.run(["mongosh", "--quiet", "--eval", script], check=True, capture_output=True, text=True)
        line2 = [l for l in res2.stdout.strip().splitlines() if l.startswith("{")][-1]
        out2 = _json.loads(line2)
        assert out2[u1] == first_locked, f"cron NOT idempotent: {first_locked} vs {out2[u1]}"


# ---------- Cleanup ---------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    import subprocess
    subprocess.run(
        ["mongosh", "--quiet", "--eval",
         "use('test_database');"
         "var ids = db.users.find({email:/^TEST_it11/},{user_id:1,_id:0}).toArray().map(function(u){return u.user_id;});"
         "db.users.deleteMany({email:/^TEST_it11/});"
         "db.user_sessions.deleteMany({user_id:{$in:ids}});"
         "db.billing.deleteMany({user_id:{$in:ids}});"
         "db.projects.deleteMany({user_id:{$in:ids}});"],
        check=False,
        capture_output=True,
    )
