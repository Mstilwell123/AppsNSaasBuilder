"""AppNSaasBuilder backend — Emergent Google Auth + local password.

Auth model (hybrid, per user choice C):
- Primary login: Emergent-managed Google Auth (session cookie).
- Layered feature: users may set a local bcrypt password they can change later
  via POST /api/auth/change-password.
"""

from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, status
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

EMERGENT_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"
SESSION_TTL_DAYS = 7
MIN_PASSWORD_LENGTH = 8
RESET_TOKEN_TTL_MINUTES = 30
OAUTH_STATE_TTL_MINUTES = 10

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


async def _send_reset_email(to_email: str, name: str, reset_link: str) -> None:
    if not resend.api_key or not SENDER_EMAIL:
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
        "from": f"{APP_NAME} <{SENDER_EMAIL}>",
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
async def login(payload: LoginIn, response: Response):
    """Sign in with email + local password. Requires the user to have a password_hash set."""
    user = await db.users.find_one({"email": payload.email.lower()}, {"_id": 0}) \
        or await db.users.find_one({"email": payload.email}, {"_id": 0})
    if not user or not user.get("password_hash"):
        # Same 401 for both to avoid account enumeration.
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
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


@api.post("/projects/{project_id}/scan", response_model=ProjectOut)
async def scan_project(project_id: str, user: dict = Depends(get_current_user)):
    proj = await _ensure_own_project(project_id, user["user_id"])
    token = await _get_github_token(user["user_id"])
    scan_id = f"scan_{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.scans.insert_one({
        "id": scan_id, "user_id": user["user_id"], "project_id": project_id,
        "status": "running", "started_at": now_iso, "finished_at": None, "error": None,
    })
    try:
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
            "user_id": user["user_id"],
            "project_id": project_id,
            "score": int(ai.get("score", 0)),
            "rationale": ai.get("rationale", ""),
            "model": SCORING_MODEL,
            "scored_at": datetime.now(timezone.utc).isoformat(),
        })
        # F3 (from handoff): carry `done: true` over to identically-worded new steps (case+whitespace-insensitive).
        old_steps = [s async for s in db.next_steps.find(
            {"project_id": project_id}, {"_id": 0},
        )]
        done_texts = {s["text"].strip().lower() for s in old_steps if s.get("done")}
        await db.next_steps.delete_many({"project_id": project_id})
        new_docs = []
        for i, step in enumerate(ai.get("next_steps", []), start=1):
            new_docs.append({
                "id": f"step_{uuid.uuid4().hex[:10]}",
                "user_id": user["user_id"],
                "project_id": project_id,
                "text": step["text"],
                "weight": step["weight"],
                "order": step.get("order", i),
                "done": step["text"].strip().lower() in done_texts,
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
                      "error": exc.detail}},
        )
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("scan failed")
        await db.scans.update_one(
            {"id": scan_id},
            {"$set": {"status": "error", "finished_at": datetime.now(timezone.utc).isoformat(),
                      "error": str(exc)[:500]}},
        )
        raise HTTPException(status_code=500, detail="Scan failed") from exc

    fresh = await db.projects.find_one({"id": project_id}, {"_id": 0})
    return await _project_to_out(fresh)


@api.patch("/next-steps/{step_id}", response_model=ProjectOut)
async def toggle_next_step(step_id: str, payload: ToggleNextStepIn, user: dict = Depends(get_current_user)):
    step = await db.next_steps.find_one({"id": step_id, "user_id": user["user_id"]}, {"_id": 0})
    if not step:
        raise HTTPException(status_code=404, detail="Next step not found")
    await db.next_steps.update_one(
        {"id": step_id},
        {"$set": {"done": bool(payload.done), "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    proj = await db.projects.find_one({"id": step["project_id"]}, {"_id": 0})
    return await _project_to_out(proj)




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
    client.close()
