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
import bcrypt
import httpx


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")

EMERGENT_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"
SESSION_TTL_DAYS = 7
MIN_PASSWORD_LENGTH = 8

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


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
