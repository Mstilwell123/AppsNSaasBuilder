# AppNSaasBuilder — Change Password Feature

## Original problem statement
Add a "Change Password" flow to the app: an authenticated `POST /api/auth/change-password`
endpoint (verify current, hash new with bcrypt, update user, rotate tokens) and an
Account/Settings screen with a form that houses it. Close the security gap left by the
publicly-exposed admin password.

## User choices captured
- **Auth architecture (choice C — hybrid):** Emergent-managed Google Auth as the primary
  login channel, layered with a *local bcrypt password* the user can set and later change.
  The local password is a hardening feature — Google remains the login channel.
- No other explicit visual preferences; using design agent output (Swiss & High-Contrast
  dark theme, Chivo + IBM Plex Sans).

## Architecture
- **Backend** (`/app/backend/server.py`, FastAPI + Motor):
  - `POST /api/auth/session` — exchanges Emergent `session_id` for a `session_token`
    cookie; upserts user (custom `user_id` field, `{_id:0}` projection everywhere).
  - `GET /api/auth/me` — returns `{ user_id, email, name, picture, has_password }`.
  - `POST /api/auth/logout` — clears cookie and deletes session row.
  - `POST /api/auth/change-password` — requires an active session. `current_password`
    is required iff the user already has one; `new_password` >= 8 chars; new must
    differ from current. On success: hashes with bcrypt, updates user, revokes all
    other sessions for this user, refreshes cookie on the current device.
  - Helpers: `hash_password`, `verify_password`, `get_current_user` (cookie → Bearer).
- **Frontend** (React 19 + react-router-dom v7 + shadcn/ui):
  - `AppRouter` synchronously detects `session_id` in URL fragment.
  - Pages: `Login` (split-screen), `AuthCallback`, `Dashboard`, `Settings`.
  - `AppShell` — sticky header with brand, nav links, and user avatar dropdown
    (Settings / Sign out).
  - `Settings` — profile card + password card. Card auto-adjusts between
    "Set a local password" (no current field) and "Change password" (with current field).
    Inline validation + sonner toasts.
  - `lib/api.js` — thin fetch wrapper (`credentials: 'include'`).
  - `lib/auth.jsx` — `AuthProvider` + `useAuth` hook.

## What's been implemented (2026-02)
- Emergent Google Auth end-to-end (session exchange, cookie, /me, logout).
- Local password: set + change flow with all validation branches.
- **Local email + password login** (`POST /api/auth/login`) — enumeration-safe.
- **Forgot password + reset password** via Resend transactional email
  (`POST /api/auth/forgot-password`, `POST /api/auth/reset-password`), sha256-hashed
  single-use tokens with 30 min TTL. Reset revokes all sessions and signs the user
  in on the new device.
- Rotate-on-change: revokes sibling sessions, keeps current device signed in.
- Settings page (profile + password) with data-testids and inline errors.
- Login page with email/password form + Google as secondary; `/forgot-password`
  and `/reset-password` pages fully wired.
- Design tokens applied globally (dark Swiss theme, Chivo/IBM Plex Sans, sharp radii).
- **CORS tightened**: `CORS_ORIGINS` env now scoped to the preview host +
  `http://localhost:3000` (was `*`). Note: platform ingress may still override
  CORS on the external URL.
- `/app/auth_testing.md` seed & curl playbook committed.

## Backlog / next
- P1: Sign-up route (email + password) — REGISTER test IDs already declared, no page yet.
- P2: Password strength meter (zxcvbn), reveal-password toggle.
- P2: Admin-only "reset another user's password" screen.
- P2: TTL index on `user_sessions.expires_at` (auto-GC).
- P2: Normalize email to lowercase at write-time so login and forgot-password
  lookups don't need casing fallbacks.
- P3: Session list + "revoke this device" per row in Settings.
- P3: Verify a custom domain in Resend so password-reset emails can be sent to
  arbitrary recipients (currently limited to the API-key owner's inbox in test mode).
