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
- **Brand rebrand**: "App N SaaS Builder" throughout header, login, emails.
- **GitHub OAuth (P2)**: `GET /api/github/{status,connect,repos}`, `GET
  /api/github/callback`, `POST /api/github/disconnect`. Tokens AES-256 encrypted
  at rest via Fernet (`TOKEN_ENCRYPTION_KEY` env). Public-repo scope only for v1
  (per PF-1). Per-user isolated.
- **Projects (P2)**: `GET/POST /api/projects`, `GET/DELETE /api/projects/{id}`.
  Track selected repos; dashboard grid of ProjectCard components.
- **AI scoring (P3)** via Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) through
  Emergent's universal LLM key: `POST /api/projects/{id}/scan` gathers
  metadata-only signals (languages, 12-week commit sparkline, CI presence,
  README presence, homepage, stars/forks/issues, license, archived) and asks
  the model for `{score 0-100, one_line_summary, rationale, next_steps[3-6]}`
  with weighted priorities. Response is JSON-parsed with fence-tolerance.
- **Polish (P4)**: 12-week commit sparkline, CI status badge
  (workflow-file presence, no Actions scope needed), live URL link,
  weighted next-steps checklist with server-side completion % (F2: no client
  drift), scan gated by confirm dialog (F3), re-scan carries over `done:true`
  for identically-worded steps (case+whitespace-insensitive), portfolio-avg
  score card on the dashboard.
- Testing agent 3× iterations, all 100% green (last: 39/39 backend + 10/10 UI).
- `/app/auth_testing.md` seed & curl playbook committed.

## Backlog / next
- P1: Sign-up route (email + password) — REGISTER test IDs already declared, no page yet.
- P2 remaining: private-repo support behind a scope-upgrade flow (PF-1 deferred).
- P2: Password strength meter (zxcvbn), reveal-password toggle.
- P2: Normalize email lowercase at write.
- P3: Session list + per-device revoke in Settings.
- P3: Verify a custom domain in Resend so password-reset emails can be sent to
  arbitrary recipients (currently limited to the API-key owner's inbox in test mode).
- **P5: Stripe billing** ($30/mo) — not built yet.
- **P6: Background scans** (queue + cron) so users don't have to press "re-scan".
- **P6: Score history chart** (already storing scores collection with `scored_at`).
- P6: Rate-limit + brief lockout on `/api/auth/login` (credential-stuffing hardening).
- P7 (nit): Store commit_sparkline as exactly 12 entries at write-time to normalise.
- P7 (nit): Serialize concurrent /scan on the same project (per-project lock).
