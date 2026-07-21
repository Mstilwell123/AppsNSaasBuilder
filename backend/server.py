"""AppNSaasBuilder backend — Emergent Google Auth + local password.

Auth model (hybrid, per user choice C):
- Primary login: Emergent-managed Google Auth (session cookie).
- Layered feature: users may set a local bcrypt password they can change later
  via POST /api/auth/change-password.
"""

from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, status
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional
import os
import uuid
import logging
import secrets
import hashlib
import asyncio
import bcrypt
import httpx
import resend


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
FRONTEND_URL = os.environ.get("FRONTEND_URL", "").rstrip("/")
APP_NAME = os.environ.get("APP_NAME", "App")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")
resend.api_key = os.environ.get("RESEND_API_KEY", "")

EMERGENT_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"
SESSION_TTL_DAYS = 7
MIN_PASSWORD_LENGTH = 8
RESET_TOKEN_TTL_MINUTES = 30

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
        await _send_reset_email(user["email"], user.get("name", ""), reset_link)
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
