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
- Auth stack: Emergent Google Auth + email/password sign-up + login + change/set
  password + forgot/reset via Resend (30-min sha256 single-use tokens).
- **Login rate-limit** (new): 5 failed attempts per email in 15 min → 429.
  `login_attempts` Mongo collection. Keyed on email only (documented — cluster
  ingress rotates upstream IPs, and attackers can rotate real IPs anyway; the
  email is the stable brute-force key).
- Settings page: profile, password, billing, weekly digest — all with data-testids.
- Login page + Google fallback + /forgot-password + /reset-password + /register.
- CORS scoped to preview host + http://localhost:3000. Brand: "App N SaaS Builder".
- GitHub OAuth (public_repo), AES-256 Fernet-encrypted tokens. Projects CRUD.
- AI scoring via Claude Haiku 4.5 (Emergent LLM key). Structured JSON.
- Polish: 12-week sparkline, CI badge, live URL, weighted next-steps checklist
  with server-side completion %, done-flag preservation on re-scan.
- **Async scan** (new): `POST /api/projects/{id}/scan` returns
  `{id, project_id, status: "running"}` immediately and runs the LLM call as an
  `asyncio.create_task`. `GET /api/scans/{scan_id}` for polling.
  Frontend polls every 2s up to 60s; toasts on completion or error.
- Score history: `GET /api/projects/{id}/scores` + SVG line chart on ProjectDetail.
- Stripe billing (P5): $30/mo Pro, 3-repo free-tier cap (402 with
  `code: "free_tier_limit_reached"`). Managed Payments (tax_mode="full").
- Top Movers widget: `GET /api/movers` + dashboard strip.
- **Streak badge** (new): `ProjectOut.streak` = consecutive strictly-increasing
  scans walking back from newest. Flame chip on ProjectCard when streak ≥ 2.
- Background jobs (APScheduler in-process): Mon 15:00 UTC weekly digest,
  03:00 UTC nightly re-scan of projects with score >24h old. `DISABLE_SCHEDULER=1`
  kills both for CI. `RESEND_FROM_DOMAIN` env for verified sender.
- Weekly Progress Digest email + opt-out + preview + send-test endpoints.
- Testing agent iterations 1–9, all green (last: 90/90 backend + 100% UI).

## Backlog / next
- **P7 (deferred, needs its own session): Split server.py into routers.**
  Current file is 1,809 lines / 32 routes / heavy cross-domain helpers
  (`get_current_user`, `db`, models). Safe plan: extract `app/deps.py` +
  `app/config.py` + `app/models.py` + `app/routers/{auth,projects,billing,digest,github}.py`
  in a dedicated session. Zero behavior change; mechanical refactor with
  after-move pytest verification per file. Also on this session: add a stale-scan
  reaper (mark `scans` rows still `running` after 5 min as `error`) — flagged
  in iteration_9 review.
- P2: Private-repo scope-upgrade flow (deferred per PF-1).
- P2: Password strength meter, reveal-password toggle.
- P3: Session list + per-device revoke in Settings.
- P3: Verify a real Resend sending domain (user-side action; docs already in place).
- P6: `resend.Emails.send` wrapped with `asyncio.wait_for(..., timeout=15)`.
