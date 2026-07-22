"""AppNSaasBuilder backend — Emergent Google Auth + local password.

Auth model (hybrid, per user choice C):
- Primary login: Emergent-managed Google Auth (session cookie).
- Layered feature: users may set a local bcrypt password they can change later
  via POST /api/auth/change-password.
"""

from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from urllib.parse import urlencode
import os
import json
import uuid
import logging
import secrets
import hashlib
import asyncio
import bcrypt
import httpx
import resend
import stripe
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from cryptography.fernet import Fernet, InvalidToken
from emergentintegrations.llm.chat import LlmChat, UserMessage


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
FRONTEND_URL = os.environ.get("FRONTEND_URL", "").rstrip("/")
APP_NAME = os.environ.get("APP_NAME", "App")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")
RESEND_FROM_DOMAIN = os.environ.get("RESEND_FROM_DOMAIN", "").strip()
resend.api_key = os.environ.get("RESEND_API_KEY", "")

GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
GITHUB_OAUTH_CALLBACK = os.environ.get("GITHUB_OAUTH_CALLBACK", "")
GITHUB_OAUTH_SCOPE = os.environ.get("GITHUB_OAUTH_SCOPE", "public_repo,read:user")
GITHUB_API = "https://api.github.com"

TOKEN_ENCRYPTION_KEY = os.environ.get("TOKEN_ENCRYPTION_KEY", "")
_fernet = Fernet(TOKEN_ENCRYPTION_KEY.encode()) if TOKEN_ENCRYPTION_KEY else None

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
SCORING_MODEL = os.environ.get("SCORING_MODEL", "claude-haiku-4-5-20251001")

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY") or "sk_test_emergent"
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRO_LOOKUP_KEY = os.environ.get("STRIPE_PRO_LOOKUP_KEY", "pro_monthly")
FREE_TIER_PROJECT_LIMIT = int(os.environ.get("FREE_TIER_PROJECT_LIMIT", "3"))

# Plan catalog — mirrors Stripe lookup_keys. Sold plans only; no free tier.
# `active_builds` gates POST /api/projects; `seats` is marketing-only for now
# (no teams feature). Trial applies to Solo Builder auto-enrolled at signup.
PLANS = {
    "solo": {
        "name": "Solo Builder",
        "blurb": "For one person shipping their own projects.",
        "price_cents": 2900,
        "active_builds": 8,
        "seats": 1,
        "features": [
            "8 builds in progress",
            "Milestone + progress tracking",
            "Deployment & status history",
            "Email support",
        ],
        "lookup_key": "appnsaas_solo_monthly",
        "trial_days": 7,
    },
    "team": {
        "name": "Team",
        "blurb": "For a small team running a lot at once.",
        "price_cents": 4900,
        "active_builds": 32,
        "seats": 4,
        "highlight": True,
        "features": [
            "32 builds in progress",
            "Up to 4 team members",
            "Client-shareable progress views",
            "Integrations & API access",
            "Priority support",
        ],
        "lookup_key": "appnsaas_team_monthly",
        "trial_days": 7,
    },
    "agency": {
        "name": "Agency",
        "blurb": "For agencies delivering builds for clients.",
        "price_cents": 14900,
        "active_builds": 200,
        "seats": 25,
        "features": [
            "200 builds in progress",
            "5 to 25 team members",
            "Client-shareable progress views",
            "Audit log & SSO-ready",
            "Dedicated support",
        ],
        "lookup_key": "appnsaas_agency_monthly",
        "trial_days": None,
    },
    "white_label": {
        "name": "White Label",
        "blurb": "Sold by conversation. Contact sales.",
        "price_cents": None,
        "active_builds": None,
        "seats": None,
        "features": [
            "Custom branding",
            "Dedicated infrastructure",
            "$1,200 setup + $499/mo",
        ],
        "lookup_key": None,
        "trial_days": None,
        "contact_only": True,
    },
}
TRIAL_PLAN_KEY = "solo"
TRIAL_DAYS = int(os.environ.get("TRIAL_DAYS", "7"))

EMERGENT_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"
SESSION_TTL_DAYS = 7
MIN_PASSWORD_LENGTH = 8
RESET_TOKEN_TTL_MINUTES = 30
OAUTH_STATE_TTL_MINUTES = 10
LOGIN_MAX_FAILS = 5
LOGIN_LOCKOUT_MINUTES = 15

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

app = FastAPI(title="AppNSaasBuilder API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# ---------- Models ----------
class UserOut(BaseModel):
    user_id: str
    email: EmailStr
    name: str
    picture: Optional[str] = None
    has_password: bool = False


class ChangePasswordIn(BaseModel):
    current_password: Optional[str] = None
    new_password: str


class SessionExchangeIn(BaseModel):
    session_id: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str
    new_password: str


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None


class PreferencesIn(BaseModel):
    weekly_digest_enabled: bool


# ---------- GitHub / Projects models ----------
class RepoOut(BaseModel):
    github_repo_id: int
    name: str
    full_name: str
    private: bool
    description: Optional[str] = None
    primary_language: Optional[str] = None
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    default_branch: str = "main"
    live_url: Optional[str] = None
    pushed_at: Optional[str] = None


class NextStepOut(BaseModel):
    id: str
    text: str
    weight: int
    done: bool
    order: int


class ScoreOut(BaseModel):
    score: int
    rationale: str
    model: str
    scored_at: str


class ProjectOut(BaseModel):
    id: str
    github_repo_id: int
    name: str
    full_name: str
    private: bool
    primary_language: Optional[str] = None
    languages: Dict[str, int] = {}
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    default_branch: str = "main"
    live_url: Optional[str] = None
    ci_status: str = "unknown"  # "configured" | "no_ci" | "unknown"
    commit_sparkline: List[int] = []
    last_commit_at: Optional[str] = None
    one_line_summary: Optional[str] = None
    added_at: str
    latest_score: Optional[ScoreOut] = None
    next_steps: List[NextStepOut] = []
    completion: int = 0  # 0..100 weighted % of next_steps done
    streak: int = 0  # consecutive scans where score strictly increased vs the prior one


class TrackRepoIn(BaseModel):
    github_repo_id: int


class ToggleNextStepIn(BaseModel):
    done: bool


# ---------- Password helpers ----------
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ---------- Session helpers ----------
def _cookie_kwargs():
    return {
        "path": "/",
        "httponly": True,
        "secure": True,
        "samesite": "none",
        "max_age": SESSION_TTL_DAYS * 24 * 3600,
    }


async def _get_session_token(request: Request) -> Optional[str]:
    token = request.cookies.get("session_token")
    if token:
        return token
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return None


async def get_current_user(request: Request) -> dict:
    token = await _get_session_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")

    expires_at = session["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")

    user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def _user_out(user: dict) -> UserOut:
    return UserOut(
        user_id=user["user_id"],
        email=user["email"],
        name=user.get("name", ""),
        picture=user.get("picture"),
        has_password=bool(user.get("password_hash")),
    )


# ---------- Local session + email helpers ----------
async def _mint_local_session(user_id: str, response: Response) -> str:
    """Create a persistent session row for a user, set the cookie, return token."""
    token = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)
    await db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": token,
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    response.set_cookie(key="session_token", value=token, **_cookie_kwargs())
    return token


def _hash_reset_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _sender_email() -> str:
    """Return the From address. Prefers verified domain (`no-reply@<domain>`) over the shared test sender."""
    if RESEND_FROM_DOMAIN:
        return f"no-reply@{RESEND_FROM_DOMAIN}"
    return SENDER_EMAIL


async def _send_reset_email(to_email: str, name: str, reset_link: str) -> None:
    if not resend.api_key or not _sender_email():
        raise HTTPException(status_code=500, detail="Email provider not configured")
    subject = f"Reset your {APP_NAME} password"
    display_name = name or to_email.split("@")[0]
    html = f"""
<!doctype html>
<html><body style="margin:0;padding:0;background:#0a0a0a;font-family:'IBM Plex Sans',Arial,sans-serif;color:#f5f5f5;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0a;">
    <tr><td align="center" style="padding:32px 16px;">
      <table role="presentation" width="480" cellpadding="0" cellspacing="0"
             style="background:#111;border:1px solid #262626;">
        <tr><td style="padding:32px;">
          <p style="margin:0 0 6px;font-size:11px;letter-spacing:.2em;text-transform:uppercase;color:#a3a3a3;">{APP_NAME}</p>
          <h1 style="margin:0 0 20px;font-family:'Chivo',Arial,sans-serif;font-size:26px;line-height:1.15;letter-spacing:-.02em;color:#fff;">Reset your password</h1>
          <p style="margin:0 0 24px;font-size:14px;line-height:1.55;color:#d4d4d4;">
            Hi {display_name}, we received a request to reset your {APP_NAME} password.
            Click the button below to choose a new one. This link expires in {RESET_TOKEN_TTL_MINUTES} minutes and can only be used once.
          </p>
          <p style="margin:0 0 24px;">
            <a href="{reset_link}" style="display:inline-block;background:#fff;color:#000;text-decoration:none;padding:12px 20px;font-weight:600;font-size:14px;border-radius:2px;">Reset password</a>
          </p>
          <p style="margin:0 0 8px;font-size:12px;color:#a3a3a3;">Or paste this link into your browser:</p>
          <p style="margin:0 0 24px;font-size:12px;color:#d4d4d4;word-break:break-all;"><a href="{reset_link}" style="color:#d4d4d4;">{reset_link}</a></p>
          <hr style="border:none;border-top:1px solid #262626;margin:24px 0;" />
          <p style="margin:0;font-size:12px;color:#a3a3a3;">If you didn't request this, you can safely ignore this email — your password will not change.</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>
"""
    text = (
        f"Reset your {APP_NAME} password\n\n"
        f"Hi {display_name},\n\n"
        f"We received a request to reset your {APP_NAME} password. "
        f"Open this link within {RESET_TOKEN_TTL_MINUTES} minutes to choose a new one (single-use):\n\n"
        f"{reset_link}\n\n"
        f"If you didn't request this, ignore this email — your password will not change.\n"
    )
    params = {
        "from": f"{APP_NAME} <{_sender_email()}>",
        "to": [to_email],
        "subject": subject,
        "html": html,
        "text": text,
    }
    try:
        await asyncio.to_thread(resend.Emails.send, params)
    except Exception as exc:  # noqa: BLE001 — surface upstream errors
        logger.error("resend send failed: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to send reset email") from exc


# ---------- Routes ----------
@api.get("/")
async def root():
    return {"message": "AppNSaasBuilder API"}


@api.post("/auth/session")
async def exchange_session(payload: SessionExchangeIn, response: Response):
    """Exchange Emergent session_id for a persistent session cookie."""
    async with httpx.AsyncClient(timeout=15.0) as http:
        resp = await http.get(EMERGENT_SESSION_URL, headers={"X-Session-ID": payload.session_id})
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid or expired session_id")
    data = resp.json()
    email = data.get("email")
    name = data.get("name", "")
    picture = data.get("picture")
    session_token = data.get("session_token")
    if not email or not session_token:
        raise HTTPException(status_code=502, detail="Malformed session response from provider")

    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        user_id = existing["user_id"]
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"name": name or existing.get("name", ""), "picture": picture,
                      "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
            "password_hash": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)
    await db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    response.set_cookie(key="session_token", value=session_token, **_cookie_kwargs())
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    return _user_out(user).model_dump()


@api.get("/auth/me", response_model=UserOut)
async def me(user: dict = Depends(get_current_user)):
    return _user_out(user)


@api.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = await _get_session_token(request)
    if token:
        await db.user_sessions.delete_many({"session_token": token})
    response.delete_cookie("session_token", path="/", samesite="none", secure=True)
    return {"ok": True}


@api.post("/auth/change-password")
async def change_password(
    payload: ChangePasswordIn,
    request: Request,
    response: Response,
    user: dict = Depends(get_current_user),
):
    """Set or change the user's local password.

    - If the user has no password yet: `current_password` is optional and ignored.
    - If the user has a password: `current_password` is required and must match.
    - `new_password` must be >= MIN_PASSWORD_LENGTH and different from the old one.
    - After a successful change, all other sessions are invalidated; the current
      cookie is refreshed so the acting user stays signed in on this device.
    """
    new_password = (payload.new_password or "").strip()
    if len(new_password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"New password must be at least {MIN_PASSWORD_LENGTH} characters")

    has_pw = bool(user.get("password_hash"))
    if has_pw:
        if not payload.current_password:
            raise HTTPException(status_code=400, detail="Current password is required")
        if not verify_password(payload.current_password, user["password_hash"]):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        if verify_password(new_password, user["password_hash"]):
            raise HTTPException(status_code=400, detail="New password must be different from the current password")

    new_hash = hash_password(new_password)
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"password_hash": new_hash, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )

    # Rotate sessions: keep this device signed in, revoke others.
    current_token = await _get_session_token(request)
    if current_token:
        await db.user_sessions.delete_many({
            "user_id": user["user_id"],
            "session_token": {"$ne": current_token},
        })
        # Refresh cookie expiry on this device.
        response.set_cookie(key="session_token", value=current_token, **_cookie_kwargs())

    return {"ok": True, "message": "Password updated"}


@api.post("/auth/login")
async def login(payload: LoginIn, request: Request, response: Response):
    """Sign in with email + local password. Requires the user to have a password_hash set.

    Rate-limited per (client-ip, email) — LOGIN_MAX_FAILS fails within LOGIN_LOCKOUT_MINUTES
    trigger a 429 lockout regardless of correctness.
    """
    email_norm = payload.email.strip().lower()
    # NOTE: keying on email alone. Cluster ingress rotates upstream client IPs, and
    # an attacker can rotate real IPs anyway; the target email is the stable key.
    window_start = (datetime.now(timezone.utc) - timedelta(minutes=LOGIN_LOCKOUT_MINUTES)).isoformat()
    recent_fails = await db.login_attempts.count_documents({
        "email": email_norm,
        "success": False,
        "created_at": {"$gte": window_start},
    })
    if recent_fails >= LOGIN_MAX_FAILS:
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed attempts. Try again in {LOGIN_LOCKOUT_MINUTES} minutes.",
        )

    async def _record(success: bool) -> None:
        await db.login_attempts.insert_one({
            "email": email_norm,
            "success": success,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    user = await db.users.find_one({"email": email_norm}, {"_id": 0}) \
        or await db.users.find_one({"email": payload.email}, {"_id": 0})
    if not user or not user.get("password_hash"):
        await _record(False)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not verify_password(payload.password, user["password_hash"]):
        await _record(False)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    await _record(True)
    await _mint_local_session(user["user_id"], response)
    return _user_out(user).model_dump()


@api.post("/auth/forgot-password")
async def forgot_password(payload: ForgotPasswordIn):
    """Generate a single-use reset token and email a reset link.

    Always returns {ok:true} to avoid revealing whether an email is registered.
    """
    user = await db.users.find_one({"email": payload.email}, {"_id": 0})
    if user:
        raw_token = secrets.token_urlsafe(48)
        token_hash = _hash_reset_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_TTL_MINUTES)
        # Invalidate any previous unused tokens for this user.
        await db.password_reset_tokens.delete_many({"user_id": user["user_id"], "used_at": None})
        await db.password_reset_tokens.insert_one({
            "user_id": user["user_id"],
            "token_hash": token_hash,
            "expires_at": expires_at.isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "used_at": None,
        })
        base = FRONTEND_URL or ""
        reset_link = f"{base}/reset-password?token={raw_token}"
        try:
            await _send_reset_email(user["email"], user.get("name", ""), reset_link)
        except HTTPException as exc:
            # Enumeration protection: never leak whether the account exists
            # via a send-side error. Log for ops; still return {ok:true}.
            logger.warning("forgot-password: send failed for user_id=%s: %s", user["user_id"], exc.detail)
    return {"ok": True}


@api.post("/auth/reset-password")
async def reset_password(payload: ResetPasswordIn, response: Response):
    """Complete a password reset. Consumes the token, updates the password, and signs the user in."""
    new_password = (payload.new_password or "").strip()
    if len(new_password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"New password must be at least {MIN_PASSWORD_LENGTH} characters")

    token_hash = _hash_reset_token(payload.token)
    token_doc = await db.password_reset_tokens.find_one({"token_hash": token_hash}, {"_id": 0})
    if not token_doc or token_doc.get("used_at"):
        raise HTTPException(status_code=400, detail="Reset link is invalid or already used")
    expires_at = token_doc["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Reset link has expired")

    user = await db.users.find_one({"user_id": token_doc["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=400, detail="Reset link is invalid or already used")

    new_hash = hash_password(new_password)
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"password_hash": new_hash, "updated_at": now_iso}},
    )
    # Consume the token + revoke any other outstanding reset tokens for this user.
    await db.password_reset_tokens.update_one(
        {"token_hash": token_hash},
        {"$set": {"used_at": now_iso}},
    )
    await db.password_reset_tokens.delete_many({
        "user_id": user["user_id"], "token_hash": {"$ne": token_hash}, "used_at": None,
    })
    # Revoke ALL existing sessions — the account was recovered, everything else must re-auth.
    await db.user_sessions.delete_many({"user_id": user["user_id"]})
    # Sign the user in on this device.
    await _mint_local_session(user["user_id"], response)
    fresh = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})
    return {"ok": True, "user": _user_out(fresh).model_dump()}


# ---------- GitHub / Projects / Scoring ----------
def _encrypt_token(raw: str) -> str:
    if not _fernet:
        raise HTTPException(status_code=500, detail="Token encryption not configured")
    return _fernet.encrypt(raw.encode("utf-8")).decode("utf-8")


def _decrypt_token(cipher: str) -> str:
    if not _fernet:
        raise HTTPException(status_code=500, detail="Token encryption not configured")
    try:
        return _fernet.decrypt(cipher.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise HTTPException(status_code=500, detail="Corrupt GitHub token") from exc


async def _get_github_token(user_id: str) -> str:
    conn = await db.github_connections.find_one({"user_id": user_id}, {"_id": 0})
    if not conn or not conn.get("encrypted_token"):
        raise HTTPException(status_code=400, detail="GitHub is not connected")
    return _decrypt_token(conn["encrypted_token"])


def _github_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _repo_to_out(repo: dict) -> RepoOut:
    return RepoOut(
        github_repo_id=repo["id"],
        name=repo["name"],
        full_name=repo["full_name"],
        private=repo.get("private", False),
        description=repo.get("description"),
        primary_language=repo.get("language"),
        stars=repo.get("stargazers_count", 0),
        forks=repo.get("forks_count", 0),
        open_issues=repo.get("open_issues_count", 0),
        default_branch=repo.get("default_branch", "main"),
        live_url=(repo.get("homepage") or None),
        pushed_at=repo.get("pushed_at"),
    )


async def _github_get(client: httpx.AsyncClient, token: str, path: str, params: Optional[dict] = None):
    url = f"{GITHUB_API}{path}" if path.startswith("/") else path
    r = await client.get(url, headers=_github_headers(token), params=params)
    if r.status_code == 404:
        return None
    if r.status_code >= 400:
        logger.warning("GitHub GET %s → %s: %s", path, r.status_code, r.text[:200])
        raise HTTPException(status_code=502, detail=f"GitHub API error ({r.status_code})")
    return r.json()


async def _gather_repo_signals(token: str, full_name: str) -> dict:
    """Read-only metadata pull from GitHub. Never fetches source."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        repo = await _github_get(client, token, f"/repos/{full_name}")
        if not repo:
            raise HTTPException(status_code=404, detail="Repo not found on GitHub")
        languages = await _github_get(client, token, f"/repos/{full_name}/languages") or {}
        # Weekly commit counts for the last ~52 weeks; take the last 12.
        stats = await _github_get(client, token, f"/repos/{full_name}/stats/participation")
        weekly = (stats or {}).get("all") or []
        sparkline = list(weekly[-12:]) if weekly else []
        # Workflow file presence (CI configured/no_ci) without needing Actions scope.
        wf = await _github_get(client, token, f"/repos/{full_name}/contents/.github/workflows")
        if isinstance(wf, list) and any((item.get("type") == "file") for item in wf):
            ci_status = "configured"
        elif wf is None:
            ci_status = "no_ci"
        else:
            ci_status = "no_ci"
        readme = await _github_get(client, token, f"/repos/{full_name}/readme")
        has_readme = bool(readme)
        return {
            "repo": repo,
            "languages": languages,
            "sparkline": sparkline,
            "ci_status": ci_status,
            "has_readme": has_readme,
        }


def _weighted_completion(steps: List[dict]) -> int:
    total = sum(int(s.get("weight", 1)) for s in steps) or 1
    done = sum(int(s.get("weight", 1)) for s in steps if s.get("done"))
    return round(100 * done / total)


def _next_step_out(doc: dict) -> NextStepOut:
    return NextStepOut(
        id=doc["id"], text=doc["text"], weight=int(doc.get("weight", 1)),
        done=bool(doc.get("done", False)), order=int(doc.get("order", 0)),
    )


async def _project_to_out(proj: dict) -> ProjectOut:
    steps_cursor = db.next_steps.find({"project_id": proj["id"]}, {"_id": 0}).sort("order", 1)
    steps = [s async for s in steps_cursor]
    latest_score_doc = await db.scores.find_one(
        {"project_id": proj["id"]}, {"_id": 0}, sort=[("scored_at", -1)],
    )
    latest = None
    if latest_score_doc:
        latest = ScoreOut(
            score=int(latest_score_doc["score"]),
            rationale=latest_score_doc.get("rationale", ""),
            model=latest_score_doc.get("model", ""),
            scored_at=latest_score_doc.get("scored_at", ""),
        )
    # Streak: count consecutive strictly-increasing scores walking back from the newest.
    recent_scores = await db.scores.find(
        {"project_id": proj["id"]}, {"_id": 0, "score": 1, "scored_at": 1},
    ).sort("scored_at", -1).to_list(length=25)
    streak = 0
    for i in range(len(recent_scores) - 1):
        if int(recent_scores[i]["score"]) > int(recent_scores[i + 1]["score"]):
            streak += 1
        else:
            break
    return ProjectOut(
        id=proj["id"],
        github_repo_id=proj["github_repo_id"],
        name=proj["name"],
        full_name=proj["full_name"],
        private=proj.get("private", False),
        primary_language=proj.get("primary_language"),
        languages=proj.get("languages", {}) or {},
        stars=proj.get("stars", 0),
        forks=proj.get("forks", 0),
        open_issues=proj.get("open_issues", 0),
        default_branch=proj.get("default_branch", "main"),
        live_url=proj.get("live_url"),
        ci_status=proj.get("ci_status", "unknown"),
        commit_sparkline=proj.get("commit_sparkline", []) or [],
        last_commit_at=proj.get("last_commit_at"),
        one_line_summary=proj.get("one_line_summary"),
        added_at=proj.get("added_at", ""),
        latest_score=latest,
        next_steps=[_next_step_out(s) for s in steps],
        completion=_weighted_completion(steps),
        streak=streak,
    )


def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of an LLM response (with or without code fences)."""
    if not text:
        raise ValueError("empty LLM response")
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        # Strip an optional language tag on the first line.
        if "\n" in t:
            first, rest = t.split("\n", 1)
            if first.strip().lower() in {"json", ""}:
                t = rest
    # Slice from first { to last } for extra robustness.
    lo, hi = t.find("{"), t.rfind("}")
    if lo == -1 or hi == -1 or hi < lo:
        raise ValueError("no JSON object found in LLM response")
    return json.loads(t[lo : hi + 1])


async def _score_with_llm(signals: dict) -> dict:
    """Ask Claude Haiku 4.5 for a 0–100 score, rationale, one-line summary, 3–6 next steps."""
    if not EMERGENT_LLM_KEY:
        raise HTTPException(status_code=500, detail="LLM key not configured")
    repo = signals["repo"]
    payload = {
        "name": repo.get("name"),
        "full_name": repo.get("full_name"),
        "description": repo.get("description"),
        "primary_language": repo.get("language"),
        "languages": signals.get("languages", {}),
        "stars": repo.get("stargazers_count", 0),
        "forks": repo.get("forks_count", 0),
        "open_issues": repo.get("open_issues_count", 0),
        "commits_last_12_weeks": signals.get("sparkline", []),
        "commits_last_12_weeks_total": sum(signals.get("sparkline") or []),
        "default_branch": repo.get("default_branch"),
        "pushed_at": repo.get("pushed_at"),
        "has_homepage": bool(repo.get("homepage")),
        "has_readme": signals.get("has_readme"),
        "ci_status": signals.get("ci_status"),  # "configured" or "no_ci"
        "license": (repo.get("license") or {}).get("spdx_id") if repo.get("license") else None,
        "archived": repo.get("archived", False),
    }
    system = (
        "You are a senior engineer scoring the *completeness* of a software project from GitHub "
        "metadata only (no source access). You must respond with ONLY a JSON object matching this "
        "schema, no prose, no markdown fences:\n"
        "{\n"
        '  "score": <int 0-100 — holistic completeness score>,\n'
        '  "one_line_summary": <string, <=100 chars, plain, no marketing fluff>,\n'
        '  "rationale": <string, 2-4 sentences citing specific signals like commit activity, CI, README, homepage, issues>,\n'
        '  "next_steps": [ {"text": <short imperative>, "weight": <int 1-5>, "order": <int, 1-indexed>} ]\n'
        "}\n"
        "next_steps must contain 3 to 6 items, prioritized (order=1 is most impactful). "
        "Weight reflects impact-on-completeness (5 = huge lift, 1 = polish). "
        "Signal-to-score guidance: recent commit activity, CI configured, README present, "
        "homepage URL set, low open-issue debt, and license all raise the score. Archived or "
        "no-commits-in-12-weeks pushes it down."
    )
    prompt = "Project signals:\n" + json.dumps(payload, indent=2) + "\nReturn the JSON object now."
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"score-{uuid.uuid4().hex[:12]}",
        system_message=system,
    ).with_model("anthropic", SCORING_MODEL)
    try:
        raw = await chat.send_message(UserMessage(text=prompt))
    except Exception as exc:  # noqa: BLE001
        logger.error("LLM call failed: %s", exc)
        raise HTTPException(status_code=502, detail="Scoring model failed") from exc
    try:
        result = _extract_json(raw if isinstance(raw, str) else str(raw))
    except Exception as exc:
        logger.error("LLM returned non-JSON: %s", raw)
        raise HTTPException(status_code=502, detail="Scoring model returned invalid JSON") from exc
    # Sanity clamp.
    result["score"] = max(0, min(100, int(result.get("score", 0))))
    steps = result.get("next_steps") or []
    if not isinstance(steps, list) or not (3 <= len(steps) <= 6):
        # Truncate / pad conservatively rather than fail — model usually gets this right.
        steps = steps[:6] if isinstance(steps, list) else []
    result["next_steps"] = [
        {
            "text": str(s.get("text", "")).strip()[:200],
            "weight": max(1, min(5, int(s.get("weight", 1)))),
            "order": int(s.get("order", i + 1)),
        }
        for i, s in enumerate(steps)
        if str(s.get("text", "")).strip()
    ]
    return result


# ---------- GitHub OAuth endpoints ----------
@api.get("/github/status")
async def github_status(user: dict = Depends(get_current_user)):
    conn = await db.github_connections.find_one({"user_id": user["user_id"]}, {"_id": 0})
    return {
        "connected": bool(conn),
        "github_username": (conn or {}).get("github_username"),
    }


@api.get("/github/connect")
async def github_connect(user: dict = Depends(get_current_user)):
    if not GITHUB_CLIENT_ID or not GITHUB_OAUTH_CALLBACK:
        raise HTTPException(status_code=500, detail="GitHub OAuth not configured")
    state = secrets.token_urlsafe(24)
    await db.github_oauth_states.insert_one({
        "state": state,
        "user_id": user["user_id"],
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=OAUTH_STATE_TTL_MINUTES)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": GITHUB_OAUTH_CALLBACK,
        "scope": GITHUB_OAUTH_SCOPE,
        "state": state,
        "allow_signup": "false",
    }
    return {"url": f"https://github.com/login/oauth/authorize?{urlencode(params)}"}


@api.get("/github/callback")
async def github_callback(code: str = "", state: str = ""):
    if not code or not state:
        return RedirectResponse(url=f"{FRONTEND_URL}/connect?error=missing_code_or_state")
    state_doc = await db.github_oauth_states.find_one({"state": state}, {"_id": 0})
    if not state_doc:
        return RedirectResponse(url=f"{FRONTEND_URL}/connect?error=invalid_state")
    # Consume the state row.
    await db.github_oauth_states.delete_many({"state": state})
    expires_at = state_doc["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return RedirectResponse(url=f"{FRONTEND_URL}/connect?error=state_expired")
    user_id = state_doc["user_id"]

    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": GITHUB_OAUTH_CALLBACK,
            },
            headers={"Accept": "application/json"},
        )
        if r.status_code != 200:
            logger.warning("github token exchange failed: %s %s", r.status_code, r.text[:200])
            return RedirectResponse(url=f"{FRONTEND_URL}/connect?error=token_exchange_failed")
        data = r.json()
        access_token = data.get("access_token")
        if not access_token:
            return RedirectResponse(url=f"{FRONTEND_URL}/connect?error=no_token")
        scopes = [s.strip() for s in (data.get("scope") or "").split(",") if s.strip()]
        me = await client.get(f"{GITHUB_API}/user", headers=_github_headers(access_token))
        if me.status_code != 200:
            return RedirectResponse(url=f"{FRONTEND_URL}/connect?error=whoami_failed")
        gh_user = me.json()

    encrypted = _encrypt_token(access_token)
    await db.github_connections.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "github_user_id": gh_user.get("id"),
            "github_username": gh_user.get("login"),
            "encrypted_token": encrypted,
            "scopes": scopes,
            "connected_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"github_connected": True, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return RedirectResponse(url=f"{FRONTEND_URL}/repos?connected=1")


@api.post("/github/disconnect")
async def github_disconnect(user: dict = Depends(get_current_user)):
    await db.github_connections.delete_many({"user_id": user["user_id"]})
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"github_connected": False}})
    return {"ok": True}


@api.get("/github/repos", response_model=List[RepoOut])
async def github_repos(user: dict = Depends(get_current_user)):
    token = await _get_github_token(user["user_id"])
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(
            f"{GITHUB_API}/user/repos",
            headers=_github_headers(token),
            params={"per_page": 100, "sort": "pushed", "affiliation": "owner"},
        )
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to list GitHub repos")
        repos = r.json()
    # v1 = public only (per PF-1)
    return [_repo_to_out(r) for r in repos if not r.get("private")]


# ---------- Projects endpoints ----------
@api.get("/projects", response_model=List[ProjectOut])
async def list_projects(user: dict = Depends(get_current_user)):
    cursor = db.projects.find({"user_id": user["user_id"]}, {"_id": 0}).sort("added_at", -1)
    projects = [p async for p in cursor]
    return [await _project_to_out(p) for p in projects]


@api.post("/projects", response_model=ProjectOut)
async def track_project(payload: TrackRepoIn, user: dict = Depends(get_current_user)):
    existing = await db.projects.find_one(
        {"user_id": user["user_id"], "github_repo_id": payload.github_repo_id},
        {"_id": 0},
    )
    if existing:
        return await _project_to_out(existing)

    # Plan-aware build-limit gate.
    resolved = await _resolve_plan(user)
    if resolved["plan_key"] == "expired":
        raise HTTPException(
            status_code=402,
            detail={
                "code": "trial_expired",
                "message": "Your trial has ended. Upgrade to continue tracking projects.",
                "trial_ends_at": resolved.get("trial_ends_at"),
            },
        )
    limit = resolved["active_builds"] or 0
    tracked = await db.projects.count_documents({"user_id": user["user_id"]})
    if tracked >= limit:
        raise HTTPException(
            status_code=402,
            detail={
                "code": "build_limit_reached",
                "message": f"Your {PLANS[resolved['plan_key']]['name']} plan is capped at {limit} builds in progress. Upgrade or complete one first.",
                "limit": limit,
                "plan_key": resolved["plan_key"],
            },
        )

    token = await _get_github_token(user["user_id"])
    async with httpx.AsyncClient(timeout=20.0) as client:
        # Look up repo by id, then hydrate signals.
        r = await client.get(
            f"{GITHUB_API}/repositories/{payload.github_repo_id}",
            headers=_github_headers(token),
        )
        if r.status_code != 200:
            raise HTTPException(status_code=404, detail="Repo not accessible")
        repo_meta = r.json()
    if repo_meta.get("private"):
        raise HTTPException(status_code=400, detail="Private repos aren't supported in v1")

    signals = await _gather_repo_signals(token, repo_meta["full_name"])
    repo = signals["repo"]
    proj_id = f"proj_{uuid.uuid4().hex[:12]}"
    doc = {
        "id": proj_id,
        "user_id": user["user_id"],
        "github_repo_id": repo["id"],
        "name": repo["name"],
        "full_name": repo["full_name"],
        "private": repo.get("private", False),
        "primary_language": repo.get("language"),
        "languages": signals["languages"],
        "stars": repo.get("stargazers_count", 0),
        "forks": repo.get("forks_count", 0),
        "open_issues": repo.get("open_issues_count", 0),
        "default_branch": repo.get("default_branch", "main"),
        "live_url": repo.get("homepage") or None,
        "ci_status": signals["ci_status"],
        "commit_sparkline": signals["sparkline"],
        "last_commit_at": repo.get("pushed_at"),
        "one_line_summary": None,
        "added_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.projects.insert_one(doc)
    return await _project_to_out(doc)


async def _ensure_own_project(project_id: str, user_id: str) -> dict:
    proj = await db.projects.find_one({"id": project_id, "user_id": user_id}, {"_id": 0})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj


@api.get("/projects/{project_id}", response_model=ProjectOut)
async def get_project(project_id: str, user: dict = Depends(get_current_user)):
    proj = await _ensure_own_project(project_id, user["user_id"])
    return await _project_to_out(proj)


@api.delete("/projects/{project_id}")
async def delete_project(project_id: str, user: dict = Depends(get_current_user)):
    await _ensure_own_project(project_id, user["user_id"])
    await db.projects.delete_many({"id": project_id, "user_id": user["user_id"]})
    await db.next_steps.delete_many({"project_id": project_id})
    await db.scores.delete_many({"project_id": project_id})
    await db.scans.delete_many({"project_id": project_id})
    return {"ok": True}


async def _run_scan(project_id: str, user_id: str, scan_id: str) -> None:
    """Body of a scan — runs in the background so the HTTP call returns immediately."""
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        proj = await db.projects.find_one({"id": project_id, "user_id": user_id}, {"_id": 0})
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found")
        token = await _get_github_token(user_id)
        signals = await _gather_repo_signals(token, proj["full_name"])
        ai = await _score_with_llm(signals)
        repo = signals["repo"]
        await db.projects.update_one(
            {"id": project_id},
            {"$set": {
                "primary_language": repo.get("language"),
                "languages": signals["languages"],
                "stars": repo.get("stargazers_count", 0),
                "forks": repo.get("forks_count", 0),
                "open_issues": repo.get("open_issues_count", 0),
                "default_branch": repo.get("default_branch", "main"),
                "live_url": repo.get("homepage") or None,
                "ci_status": signals["ci_status"],
                "commit_sparkline": signals["sparkline"],
                "last_commit_at": repo.get("pushed_at"),
                "one_line_summary": ai.get("one_line_summary"),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        await db.scores.insert_one({
            "id": f"score_{uuid.uuid4().hex[:12]}",
            "user_id": user_id,
            "project_id": project_id,
            "score": int(ai.get("score", 0)),
            "rationale": ai.get("rationale", ""),
            "model": SCORING_MODEL,
            "scored_at": datetime.now(timezone.utc).isoformat(),
        })
        old_steps = [s async for s in db.next_steps.find(
            {"project_id": project_id}, {"_id": 0},
        )]
        done_texts = {s["text"].strip().lower() for s in old_steps if s.get("done")}
        completed_at_map = {
            s["text"].strip().lower(): s.get("completed_at")
            for s in old_steps
            if s.get("done") and s.get("completed_at")
        }
        await db.next_steps.delete_many({"project_id": project_id})
        new_docs = []
        for i, step in enumerate(ai.get("next_steps", []), start=1):
            key = step["text"].strip().lower()
            is_done = key in done_texts
            new_docs.append({
                "id": f"step_{uuid.uuid4().hex[:10]}",
                "user_id": user_id,
                "project_id": project_id,
                "text": step["text"],
                "weight": step["weight"],
                "order": step.get("order", i),
                "done": is_done,
                "completed_at": completed_at_map.get(key) if is_done else None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        if new_docs:
            await db.next_steps.insert_many(new_docs)
        await db.scans.update_one(
            {"id": scan_id},
            {"$set": {"status": "done", "finished_at": datetime.now(timezone.utc).isoformat()}},
        )
    except HTTPException as exc:
        await db.scans.update_one(
            {"id": scan_id},
            {"$set": {"status": "error", "finished_at": datetime.now(timezone.utc).isoformat(),
                      "error": exc.detail if isinstance(exc.detail, str) else "Scan failed"}},
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("background scan failed")
        await db.scans.update_one(
            {"id": scan_id},
            {"$set": {"status": "error", "finished_at": datetime.now(timezone.utc).isoformat(),
                      "error": str(exc)[:500]}},
        )


class ScanOut(BaseModel):
    id: str
    project_id: str
    status: str  # "running" | "done" | "error"
    started_at: str
    finished_at: Optional[str] = None
    error: Optional[str] = None


@api.post("/projects/{project_id}/scan", response_model=ScanOut)
async def scan_project(project_id: str, user: dict = Depends(get_current_user)):
    """Kick off a scan in the background. Client should poll GET /api/scans/{id}."""
    proj = await _ensure_own_project(project_id, user["user_id"])
    # Guard: ensure GitHub is connected before scheduling — cheaper to fail here.
    await _get_github_token(user["user_id"])
    scan_id = f"scan_{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.scans.insert_one({
        "id": scan_id, "user_id": user["user_id"], "project_id": project_id,
        "status": "running", "started_at": now_iso, "finished_at": None, "error": None,
    })
    # Fire and forget — the endpoint responds while the coroutine runs on the loop.
    asyncio.create_task(_run_scan(project_id, user["user_id"], scan_id))
    return ScanOut(id=scan_id, project_id=project_id, status="running", started_at=now_iso)


@api.get("/scans/{scan_id}", response_model=ScanOut)
async def get_scan(scan_id: str, user: dict = Depends(get_current_user)):
    doc = await db.scans.find_one(
        {"id": scan_id, "user_id": user["user_id"]}, {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Scan not found")
    return ScanOut(
        id=doc["id"], project_id=doc["project_id"], status=doc.get("status", "running"),
        started_at=doc.get("started_at", ""), finished_at=doc.get("finished_at"),
        error=doc.get("error"),
    )


@api.patch("/next-steps/{step_id}", response_model=ProjectOut)
async def toggle_next_step(step_id: str, payload: ToggleNextStepIn, user: dict = Depends(get_current_user)):
    step = await db.next_steps.find_one({"id": step_id, "user_id": user["user_id"]}, {"_id": 0})
    if not step:
        raise HTTPException(status_code=404, detail="Next step not found")
    now_iso = datetime.now(timezone.utc).isoformat()
    update = {"done": bool(payload.done), "updated_at": now_iso}
    # Stamp completed_at only on the first done→true transition and when re-completing;
    # unset when marked back to not-done so the weekly-activity count is truthful.
    if payload.done and not step.get("completed_at"):
        update["completed_at"] = now_iso
    if not payload.done and step.get("completed_at"):
        update["completed_at"] = None
    await db.next_steps.update_one({"id": step_id}, {"$set": update})
    proj = await db.projects.find_one({"id": step["project_id"]}, {"_id": 0})
    return await _project_to_out(proj)


@api.get("/activity/weekly")
async def activity_weekly(user: dict = Depends(get_current_user)):
    """Return this user's shipping activity in the last 7 days.

    A "shipped" step is any next-step marked done whose `completed_at` falls within
    the last 7 days. Threshold (3) drives the Dashboard "shipped this week" badge.
    """
    since_iso = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    count = await db.next_steps.count_documents({
        "user_id": user["user_id"],
        "done": True,
        "completed_at": {"$gte": since_iso},
    })
    return {"shipped_this_week": int(count), "threshold": 3, "window_days": 7}




# ---------- Top Movers ----------
class MoverOut(BaseModel):
    project_id: str
    name: str
    full_name: str
    latest_score: int
    previous_score: int
    delta: int
    scored_at: str
    previous_scored_at: str


@api.get("/movers", response_model=List[MoverOut])
async def top_movers(
    limit: int = 3,
    user: dict = Depends(get_current_user),
):
    """Projects whose latest score changed the most vs their previous scan.

    Only projects with at least two recorded scores are eligible. Sorted by
    absolute delta descending; ties broken by most recent scored_at.
    """
    limit = max(1, min(20, int(limit)))
    projects = [p async for p in db.projects.find(
        {"user_id": user["user_id"]}, {"_id": 0, "id": 1, "name": 1, "full_name": 1},
    )]
    movers: List[dict] = []
    for p in projects:
        recent = await db.scores.find(
            {"project_id": p["id"]}, {"_id": 0}, sort=[("scored_at", -1)],
        ).to_list(length=2)
        if len(recent) < 2:
            continue
        latest, previous = recent[0], recent[1]
        delta = int(latest["score"]) - int(previous["score"])
        if delta == 0:
            continue
        movers.append({
            "project_id": p["id"],
            "name": p["name"],
            "full_name": p["full_name"],
            "latest_score": int(latest["score"]),
            "previous_score": int(previous["score"]),
            "delta": delta,
            "scored_at": latest["scored_at"],
            "previous_scored_at": previous["scored_at"],
        })
    movers.sort(key=lambda m: (-abs(m["delta"]), -1 if m["scored_at"] else 0), reverse=False)
    # Above uses negative absolute delta as primary key (ascending sort of negatives = largest first).
    return movers[:limit]




# ---------- Billing (Stripe subscription) ----------
class BillingCheckoutIn(BaseModel):
    origin_url: str
    plan_key: Optional[str] = None  # "solo" | "team" | "agency"


@api.get("/billing/plans")
async def billing_plans():
    """Public: returns marketing catalog for the pricing page."""
    out = []
    for key, p in PLANS.items():
        out.append({
            "plan_key": key,
            "name": p["name"],
            "blurb": p["blurb"],
            "price_cents": p["price_cents"],
            "active_builds": p["active_builds"],
            "seats": p["seats"],
            "features": p["features"],
            "trial_days": p.get("trial_days"),
            "highlight": bool(p.get("highlight")),
            "contact_only": bool(p.get("contact_only")),
            "lookup_key": p["lookup_key"],
        })
    return {"plans": out}


@api.get("/billing/subscription")
async def billing_subscription(user: dict = Depends(get_current_user)):
    resolved = await _resolve_plan(user)
    tracked = await db.projects.count_documents({"user_id": user["user_id"]})
    plan_meta = PLANS.get(resolved["plan_key"])
    return {
        "plan_key": resolved["plan_key"],
        "source": resolved["source"],  # "stripe" | "trial" | "none"
        "plan_name": plan_meta["name"] if plan_meta else None,
        "active_builds_limit": resolved["active_builds"],
        "tracked_projects": tracked,
        "trial_ends_at": resolved.get("trial_ends_at"),
        "current_period_end": resolved.get("current_period_end"),
        "cancel_at_period_end": resolved.get("cancel_at_period_end"),
    }


def _plan_for(billing: Optional[dict]) -> str:
    if not billing:
        return "none"
    status = (billing.get("subscription_status") or "").lower()
    if status in {"active", "trialing"}:
        return billing.get("plan_key") or "solo"
    return "none"


async def _resolve_plan(user: dict) -> dict:
    """Return {plan_key, source, active_builds, trial_ends_at, expires_at}.

    Precedence: active Stripe subscription > in-trial user > expired/no plan.
    """
    b = await db.billing.find_one({"user_id": user["user_id"]}, {"_id": 0})
    stripe_plan = _plan_for(b)
    if stripe_plan != "none":
        p = PLANS.get(stripe_plan, PLANS["solo"])
        return {
            "plan_key": stripe_plan, "source": "stripe",
            "active_builds": p["active_builds"],
            "current_period_end": (b or {}).get("current_period_end"),
            "cancel_at_period_end": bool((b or {}).get("cancel_at_period_end")),
            "trial_ends_at": None,
        }
    # Fall back to sign-up trial.
    trial_ends_at = user.get("trial_ends_at")
    if trial_ends_at:
        end = trial_ends_at
        if isinstance(end, str):
            end = datetime.fromisoformat(end)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        if end > datetime.now(timezone.utc):
            p = PLANS[TRIAL_PLAN_KEY]
            return {
                "plan_key": TRIAL_PLAN_KEY, "source": "trial",
                "active_builds": p["active_builds"],
                "trial_ends_at": trial_ends_at,
                "current_period_end": None, "cancel_at_period_end": False,
            }
    return {
        "plan_key": "expired", "source": "none",
        "active_builds": 0,
        "trial_ends_at": trial_ends_at, "current_period_end": None,
        "cancel_at_period_end": False,
    }


async def _get_plan(user_id: str) -> str:
    u = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not u:
        return "none"
    r = await _resolve_plan(u)
    return r["plan_key"]


@api.get("/billing/status")
async def billing_status(user: dict = Depends(get_current_user)):
    b = await db.billing.find_one({"user_id": user["user_id"]}, {"_id": 0})
    plan = _plan_for(b)
    tracked = await db.projects.count_documents({"user_id": user["user_id"]})
    return {
        "plan": plan,
        "subscription_status": (b or {}).get("subscription_status"),
        "current_period_end": (b or {}).get("current_period_end"),
        "cancel_at_period_end": bool((b or {}).get("cancel_at_period_end")),
        "customer_id": (b or {}).get("customer_id"),
        "subscription_id": (b or {}).get("subscription_id"),
        "tracked_projects": tracked,
        "free_tier_limit": FREE_TIER_PROJECT_LIMIT,
    }


async def _get_or_create_customer(user: dict) -> str:
    b = await db.billing.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if b and b.get("customer_id"):
        return b["customer_id"]
    customer = await asyncio.to_thread(
        stripe.Customer.create,
        email=user["email"],
        name=user.get("name") or user["email"],
        metadata={"user_id": user["user_id"]},
    )
    await db.billing.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"user_id": user["user_id"], "customer_id": customer.id,
                  "email": user["email"],
                  "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return customer.id


@api.post("/billing/checkout")
async def billing_checkout(payload: BillingCheckoutIn, user: dict = Depends(get_current_user)):
    # Resolve which plan the caller wants; default to solo if not specified.
    plan_key = (payload.plan_key or TRIAL_PLAN_KEY).lower()
    plan = PLANS.get(plan_key)
    if not plan or not plan.get("lookup_key"):
        raise HTTPException(status_code=400, detail=f"Unknown or non-checkoutable plan: {plan_key}")
    prices = await asyncio.to_thread(
        lambda: stripe.Price.list(lookup_keys=[plan["lookup_key"]], active=True, limit=1).data,
    )
    if not prices:
        raise HTTPException(status_code=500, detail=f"Price for {plan_key} not configured")
    price = prices[0]

    customer_id = await _get_or_create_customer(user)

    origin = payload.origin_url.rstrip("/")
    kwargs = dict(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price.id, "quantity": 1}],
        success_url=f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{origin}/payment/cancel",
        metadata={"user_id": user["user_id"], "lookup_key": plan["lookup_key"], "plan_key": plan_key},
        allow_promotion_codes=True,
    )
    try:
        session = await asyncio.to_thread(
            lambda: stripe.checkout.Session.create(**kwargs, managed_payments={"enabled": True}),
        )
    except stripe.error.InvalidRequestError as e:
        msg = (getattr(e, "user_message", "") or "").lower()
        if "managed payments" in msg or "ineligible" in msg:
            session = await asyncio.to_thread(
                lambda: stripe.checkout.Session.create(
                    **kwargs, automatic_tax={"enabled": True}, billing_address_collection="required",
                ),
            )
        else:
            raise HTTPException(status_code=502, detail=str(e))

    await db.payment_transactions.insert_one({
        "session_id": session.id,
        "user_id": user["user_id"],
        "customer_id": customer_id,
        "lookup_key": plan["lookup_key"],
        "plan_key": plan_key,
        "amount": (price.unit_amount or 0),
        "currency": price.currency,
        "status": "initiated",
        "payment_status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"checkout_url": session.url, "session_id": session.id}


@api.get("/payments/status/{session_id}")
async def payments_status(session_id: str):
    record = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if record.get("payment_status") != "paid":
        try:
            s = await asyncio.to_thread(stripe.checkout.Session.retrieve, session_id)
            if s.payment_status == "paid" or s.status == "complete":
                await db.payment_transactions.update_one(
                    {"session_id": session_id, "payment_status": {"$ne": "paid"}},
                    {"$set": {
                        "status": "completed",
                        "payment_status": "paid",
                        "subscription_id": s.subscription,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }},
                )
                record = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
        except Exception as exc:  # noqa: BLE001
            logger.warning("stripe status poll failed: %s", exc)
    return {
        "session_id": record["session_id"],
        "status": record["status"],
        "payment_status": record["payment_status"],
    }


@api.post("/billing/portal")
async def billing_portal(payload: BillingCheckoutIn, user: dict = Depends(get_current_user)):
    b = await db.billing.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if not b or not b.get("customer_id"):
        raise HTTPException(status_code=400, detail="No billing profile yet")
    origin = payload.origin_url.rstrip("/")
    portal = await asyncio.to_thread(
        stripe.billing_portal.Session.create,
        customer=b["customer_id"],
        return_url=f"{origin}/settings",
    )
    return {"url": portal.url}


async def _apply_subscription_state(customer_id: str, subscription: dict) -> None:
    sub_id = subscription.get("id")
    status = subscription.get("status")
    cancel_at_period_end = bool(subscription.get("cancel_at_period_end"))
    period_end = subscription.get("current_period_end")
    now_iso = datetime.now(timezone.utc).isoformat()
    period_end_iso = None
    if period_end:
        period_end_iso = datetime.fromtimestamp(int(period_end), tz=timezone.utc).isoformat()
    # Derive plan_key from the subscription's first line item lookup_key.
    plan_key = None
    try:
        items = subscription.get("items", {}).get("data", []) or []
        if items:
            lookup = (items[0].get("price") or {}).get("lookup_key")
            for k, v in PLANS.items():
                if v.get("lookup_key") == lookup:
                    plan_key = k
                    break
    except Exception:  # noqa: BLE001
        pass
    update = {
        "customer_id": customer_id,
        "subscription_id": sub_id,
        "subscription_status": status,
        "cancel_at_period_end": cancel_at_period_end,
        "current_period_end": period_end_iso,
        "updated_at": now_iso,
    }
    if plan_key:
        update["plan_key"] = plan_key
    await db.billing.update_one(
        {"customer_id": customer_id}, {"$set": update}, upsert=True,
    )


@api.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    obj = event["data"]["object"]
    t = event["type"]

    if t == "checkout.session.completed":
        await db.payment_transactions.update_one(
            {"session_id": obj["id"], "payment_status": {"$ne": "paid"}},
            {"$set": {
                "status": "completed",
                "payment_status": obj.get("payment_status", "paid"),
                "subscription_id": obj.get("subscription"),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        sub_id = obj.get("subscription")
        customer_id = obj.get("customer")
        if sub_id and customer_id:
            sub = await asyncio.to_thread(stripe.Subscription.retrieve, sub_id)
            await _apply_subscription_state(customer_id, sub.to_dict())
    elif t == "checkout.session.async_payment_succeeded":
        await db.payment_transactions.update_one(
            {"session_id": obj["id"]},
            {"$set": {"payment_status": "paid",
                      "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
    elif t == "checkout.session.async_payment_failed":
        await db.payment_transactions.update_one(
            {"session_id": obj["id"]},
            {"$set": {"status": "failed", "payment_status": "failed",
                      "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
    elif t in {"customer.subscription.created", "customer.subscription.updated"}:
        await _apply_subscription_state(obj.get("customer"), obj)
    elif t == "customer.subscription.deleted":
        await db.billing.update_one(
            {"customer_id": obj.get("customer")},
            {"$set": {
                "subscription_status": "canceled",
                "cancel_at_period_end": False,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
    elif t == "charge.refunded":
        await db.payment_transactions.update_one(
            {"stripe_payment_intent_id": obj.get("payment_intent")},
            {"$set": {"status": "refunded", "payment_status": "refunded",
                      "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
    return {"status": "ok"}




# ---------- Sign-up (email + password) ----------
@api.post("/auth/register")
async def register(payload: RegisterIn, response: Response):
    email = payload.email.strip().lower()
    password = (payload.password or "").strip()
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        # Enumeration-safe generic message.
        raise HTTPException(status_code=409, detail="An account with that email already exists")
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    trial_ends_at = (datetime.now(timezone.utc) + timedelta(days=TRIAL_DAYS)).isoformat()
    await db.users.insert_one({
        "user_id": user_id,
        "email": email,
        "name": (payload.name or "").strip() or email.split("@")[0],
        "picture": None,
        "password_hash": hash_password(password),
        "weekly_digest_enabled": True,
        "trial_started_at": now_iso,
        "trial_ends_at": trial_ends_at,
        "created_at": now_iso,
        "updated_at": now_iso,
    })
    await _mint_local_session(user_id, response)
    fresh = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    return _user_out(fresh).model_dump()


# ---------- Preferences ----------
@api.get("/preferences")
async def get_preferences(user: dict = Depends(get_current_user)):
    return {"weekly_digest_enabled": bool(user.get("weekly_digest_enabled", True))}


@api.patch("/preferences")
async def update_preferences(payload: PreferencesIn, user: dict = Depends(get_current_user)):
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"weekly_digest_enabled": bool(payload.weekly_digest_enabled),
                  "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"weekly_digest_enabled": bool(payload.weekly_digest_enabled)}


# ---------- Score history ----------
class ScoreHistoryOut(BaseModel):
    score: int
    scored_at: str
    rationale: Optional[str] = None


@api.get("/projects/{project_id}/scores", response_model=List[ScoreHistoryOut])
async def score_history(project_id: str, limit: int = 20, user: dict = Depends(get_current_user)):
    await _ensure_own_project(project_id, user["user_id"])
    limit = max(1, min(100, int(limit)))
    docs = await db.scores.find(
        {"project_id": project_id}, {"_id": 0},
    ).sort("scored_at", -1).to_list(length=limit)
    docs.reverse()  # chronological for charts
    return [ScoreHistoryOut(
        score=int(d["score"]), scored_at=d.get("scored_at", ""), rationale=d.get("rationale"),
    ) for d in docs]


# ---------- Progress Digest ----------
async def _build_digest_for_user(user: dict) -> Optional[dict]:
    """Return a dict {subject, html, text, movers, avg, deltas} or None if the user has nothing to digest."""
    projects = [p async for p in db.projects.find(
        {"user_id": user["user_id"]}, {"_id": 0},
    )]
    if not projects:
        return None

    # Portfolio average — most recent score per project.
    scored: List[dict] = []
    for p in projects:
        latest = await db.scores.find_one(
            {"project_id": p["id"]}, {"_id": 0}, sort=[("scored_at", -1)],
        )
        if latest:
            scored.append({"project": p, "latest": latest})
    if not scored:
        return None
    avg = round(sum(int(s["latest"]["score"]) for s in scored) / len(scored))

    # Movers this week: delta between latest and second-latest, restricted to 7-day window.
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    movers: List[dict] = []
    for s in scored:
        recent = await db.scores.find(
            {"project_id": s["project"]["id"]}, {"_id": 0},
        ).sort("scored_at", -1).to_list(length=2)
        if len(recent) < 2:
            continue
        # Only include if the latest scan is within the digest window.
        if recent[0]["scored_at"] < since:
            continue
        delta = int(recent[0]["score"]) - int(recent[1]["score"])
        if delta == 0:
            continue
        movers.append({
            "name": s["project"]["name"],
            "full_name": s["project"]["full_name"],
            "delta": delta,
            "latest": int(recent[0]["score"]),
            "previous": int(recent[1]["score"]),
        })
    movers.sort(key=lambda m: -abs(m["delta"]))
    top_movers = movers[:3]

    # Completed steps this week.
    completed_cursor = db.next_steps.find({
        "user_id": user["user_id"], "done": True,
        "updated_at": {"$gte": since},
    }, {"_id": 0})
    completed_this_week = await completed_cursor.to_list(length=100)

    subject = f"Your {APP_NAME} weekly digest — {avg}/100 avg"
    first_name = (user.get("name") or user["email"].split("@")[0]).split(" ")[0]
    dashboard_url = f"{FRONTEND_URL}/dashboard" if FRONTEND_URL else "#"

    def _mover_row(m):
        up = m["delta"] > 0
        color = "#6ee7b7" if up else "#fca5a5"
        arrow = "▲" if up else "▼"
        return (
            f'<tr><td style="padding:8px 0;border-top:1px solid #262626;">'
            f'<div style="color:#f5f5f5;font-size:14px;">{m["name"]}</div>'
            f'<div style="color:#a3a3a3;font-size:11px;">{m["full_name"]}</div>'
            f'</td>'
            f'<td style="padding:8px 0;border-top:1px solid #262626;text-align:right;">'
            f'<span style="color:{color};font-size:14px;font-weight:600;">{arrow} {abs(m["delta"])}</span>'
            f'<div style="color:#a3a3a3;font-size:11px;">{m["previous"]} → {m["latest"]}</div>'
            f'</td></tr>'
        )

    movers_html = "".join(_mover_row(m) for m in top_movers) if top_movers else (
        '<tr><td colspan="2" style="padding:8px 0;color:#a3a3a3;font-size:12px;">'
        "No movers this week — kick off a scan to refresh signals.</td></tr>"
    )
    completed_html = ""
    if completed_this_week:
        rows = "".join(
            f'<li style="color:#d4d4d4;font-size:13px;margin:4px 0;">✓ {s["text"]}</li>'
            for s in completed_this_week[:6]
        )
        completed_html = (
            '<div style="margin-top:24px;">'
            '<p style="margin:0 0 8px;font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:#a3a3a3;">Shipped this week</p>'
            f'<ul style="list-style:none;padding:0;margin:0;">{rows}</ul></div>'
        )

    html = f"""
<!doctype html>
<html><body style="margin:0;padding:0;background:#0a0a0a;font-family:'IBM Plex Sans',Arial,sans-serif;color:#f5f5f5;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0a;">
    <tr><td align="center" style="padding:32px 16px;">
      <table role="presentation" width="520" cellpadding="0" cellspacing="0" style="background:#111;border:1px solid #262626;">
        <tr><td style="padding:32px;">
          <p style="margin:0 0 6px;font-size:11px;letter-spacing:.2em;text-transform:uppercase;color:#a3a3a3;">{APP_NAME} · weekly digest</p>
          <h1 style="margin:0 0 20px;font-family:'Chivo',Arial,sans-serif;font-size:26px;line-height:1.15;letter-spacing:-.02em;color:#fff;">Hey {first_name}, your portfolio at a glance.</h1>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:12px 0 20px;">
            <tr>
              <td style="width:50%;padding:12px;border:1px solid #262626;">
                <div style="font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:#a3a3a3;">Avg score</div>
                <div style="font-family:'Chivo',Arial,sans-serif;font-size:32px;color:#fff;margin-top:4px;">{avg}<span style="font-size:14px;color:#a3a3a3;">/100</span></div>
              </td>
              <td style="width:50%;padding:12px;border:1px solid #262626;border-left:none;">
                <div style="font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:#a3a3a3;">Tracked repos</div>
                <div style="font-family:'Chivo',Arial,sans-serif;font-size:32px;color:#fff;margin-top:4px;">{len(projects)}</div>
              </td>
            </tr>
          </table>
          <p style="margin:0 0 8px;font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:#a3a3a3;">Top movers</p>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{movers_html}</table>
          {completed_html}
          <p style="margin:28px 0 0;">
            <a href="{dashboard_url}" style="display:inline-block;background:#fff;color:#000;text-decoration:none;padding:12px 20px;font-weight:600;font-size:14px;border-radius:2px;">Open dashboard</a>
          </p>
          <hr style="border:none;border-top:1px solid #262626;margin:28px 0;" />
          <p style="margin:0;font-size:11px;color:#a3a3a3;">You're receiving this because weekly digests are enabled. <a href="{FRONTEND_URL}/settings" style="color:#a3a3a3;">Turn them off in Settings.</a></p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>
"""
    text_parts = [
        f"{APP_NAME} weekly digest",
        f"Avg score: {avg}/100 across {len(projects)} repos",
        "",
        "Top movers:",
    ]
    if top_movers:
        for m in top_movers:
            sign = "+" if m["delta"] > 0 else ""
            text_parts.append(f"  - {m['name']}: {m['previous']} -> {m['latest']} ({sign}{m['delta']})")
    else:
        text_parts.append("  (none this week)")
    text_parts.extend(["", f"Open: {dashboard_url}"])
    text = "\n".join(text_parts)
    return {
        "subject": subject,
        "html": html,
        "text": text,
        "avg": avg,
        "movers": top_movers,
        "completed_count": len(completed_this_week),
        "tracked_count": len(projects),
    }


async def _send_email(to_email: str, subject: str, html: str, text: str) -> None:
    if not resend.api_key or not _sender_email():
        raise HTTPException(status_code=500, detail="Email provider not configured")
    params = {
        "from": f"{APP_NAME} <{_sender_email()}>",
        "to": [to_email], "subject": subject, "html": html, "text": text,
    }
    await asyncio.to_thread(resend.Emails.send, params)


@api.get("/digest/preview")
async def digest_preview(user: dict = Depends(get_current_user)):
    digest = await _build_digest_for_user(user)
    if not digest:
        return {"available": False}
    return {"available": True, **digest}


@api.post("/digest/send-test")
async def digest_send_test(user: dict = Depends(get_current_user)):
    """Send this user their own digest right now — useful for verifying Resend domain."""
    digest = await _build_digest_for_user(user)
    if not digest:
        raise HTTPException(status_code=400, detail="Nothing to digest yet — track a project and run a scan first.")
    try:
        await _send_email(user["email"], digest["subject"], digest["html"], digest["text"])
    except Exception as exc:  # noqa: BLE001
        logger.error("digest send-test failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Send failed: {exc}") from exc
    return {"ok": True}


# ---------- Background jobs (APScheduler) ----------
_scheduler: Optional[AsyncIOScheduler] = None


async def _job_send_weekly_digests() -> None:
    """Mondays 15:00 UTC — send Progress Digest to opted-in users with >=1 project."""
    logger.info("weekly digest job: starting")
    sent = 0
    async for user in db.users.find({"weekly_digest_enabled": {"$ne": False}}, {"_id": 0}):
        try:
            digest = await _build_digest_for_user(user)
            if not digest:
                continue
            await _send_email(user["email"], digest["subject"], digest["html"], digest["text"])
            sent += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("digest to %s failed: %s", user.get("email"), exc)
    logger.info("weekly digest job: sent %d", sent)


async def _job_rescan_stale_projects() -> None:
    """Nightly 03:00 UTC — re-scan projects whose latest score is older than 24h."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    logger.info("nightly rescan job: cutoff=%s", cutoff)
    scanned = 0
    async for proj in db.projects.find({}, {"_id": 0}):
        latest = await db.scores.find_one(
            {"project_id": proj["id"]}, {"_id": 0}, sort=[("scored_at", -1)],
        )
        if latest and latest.get("scored_at", "") > cutoff:
            continue
        try:
            token = await _get_github_token(proj["user_id"])
        except HTTPException:
            continue  # user disconnected GitHub
        try:
            signals = await _gather_repo_signals(token, proj["full_name"])
            ai = await _score_with_llm(signals)
            repo = signals["repo"]
            now_iso = datetime.now(timezone.utc).isoformat()
            await db.projects.update_one(
                {"id": proj["id"]},
                {"$set": {
                    "primary_language": repo.get("language"),
                    "languages": signals["languages"],
                    "stars": repo.get("stargazers_count", 0),
                    "forks": repo.get("forks_count", 0),
                    "open_issues": repo.get("open_issues_count", 0),
                    "live_url": repo.get("homepage") or None,
                    "ci_status": signals["ci_status"],
                    "commit_sparkline": signals["sparkline"],
                    "last_commit_at": repo.get("pushed_at"),
                    "one_line_summary": ai.get("one_line_summary"),
                    "updated_at": now_iso,
                }},
            )
            await db.scores.insert_one({
                "id": f"score_{uuid.uuid4().hex[:12]}",
                "user_id": proj["user_id"],
                "project_id": proj["id"],
                "score": int(ai.get("score", 0)),
                "rationale": ai.get("rationale", ""),
                "model": SCORING_MODEL,
                "scored_at": now_iso,
            })
            # Preserve done-flags and completed_at for identically-worded steps (F3).
            old_steps = [s async for s in db.next_steps.find(
                {"project_id": proj["id"]}, {"_id": 0},
            )]
            done_texts = {s["text"].strip().lower() for s in old_steps if s.get("done")}
            completed_at_map = {
                s["text"].strip().lower(): s.get("completed_at")
                for s in old_steps
                if s.get("done") and s.get("completed_at")
            }
            await db.next_steps.delete_many({"project_id": proj["id"]})
            new_docs = []
            for i, step in enumerate(ai.get("next_steps", []), start=1):
                key = step["text"].strip().lower()
                is_done = key in done_texts
                new_docs.append({
                    "id": f"step_{uuid.uuid4().hex[:10]}",
                    "user_id": proj["user_id"],
                    "project_id": proj["id"],
                    "text": step["text"],
                    "weight": step["weight"],
                    "order": step.get("order", i),
                    "done": is_done,
                    "completed_at": completed_at_map.get(key) if is_done else None,
                    "created_at": now_iso,
                })
            if new_docs:
                await db.next_steps.insert_many(new_docs)
            scanned += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("nightly rescan for %s failed: %s", proj.get("full_name"), exc)
    logger.info("nightly rescan job: scanned %d", scanned)


async def _job_lock_expired_trials() -> None:
    """Nightly 04:00 UTC — mark users whose 7-day trial expired and who have no active
    Stripe subscription as ``locked``. Idempotent: skips already-locked users."""
    now_iso = datetime.now(timezone.utc).isoformat()
    logger.info("trial lock job: cutoff=%s", now_iso)
    locked = 0
    async for user in db.users.find(
        {
            "trial_ends_at": {"$lt": now_iso},
            "locked_at": {"$in": [None, ""]},
        },
        {"_id": 0},
    ):
        # Skip if user has an active/trialing Stripe subscription.
        b = await db.billing.find_one({"user_id": user["user_id"]}, {"_id": 0})
        status = ((b or {}).get("subscription_status") or "").lower()
        if status in {"active", "trialing"}:
            continue
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"locked_at": now_iso, "updated_at": now_iso}},
        )
        locked += 1
    logger.info("trial lock job: locked %d user(s)", locked)


@app.on_event("startup")
async def _startup_scheduler():
    global _scheduler
    if os.environ.get("DISABLE_SCHEDULER") == "1":
        logger.info("scheduler disabled via env")
        return
    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(_job_send_weekly_digests, CronTrigger(day_of_week="mon", hour=15, minute=0),
                       id="weekly_digest", replace_existing=True)
    _scheduler.add_job(_job_rescan_stale_projects, CronTrigger(hour=3, minute=0),
                       id="nightly_rescan", replace_existing=True)
    _scheduler.add_job(_job_lock_expired_trials, CronTrigger(hour=4, minute=0),
                       id="trial_lock", replace_existing=True)
    _scheduler.start()
    logger.info("scheduler started: weekly_digest (mon 15:00 UTC), nightly_rescan (03:00 UTC), trial_lock (04:00 UTC)")




app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=CORS_ORIGINS if CORS_ORIGINS else [],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            pass
    client.close()
