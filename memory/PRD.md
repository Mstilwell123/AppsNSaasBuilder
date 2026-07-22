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
- Local email + password login (`POST /api/auth/login`), enumeration-safe.
- **Email/password sign-up** (`POST /api/auth/register`), lowercase-normalized email,
  duplicate → 409, min-8 pw, immediate session on success. `/register` page + link
  from `/login`.
- Forgot password + reset password via Resend (30-min single-use sha256 tokens).
- Settings page (profile + password + billing + weekly digest) with data-testids.
- Login page with email/password form + Google as secondary; /forgot-password,
  /reset-password, /register pages fully wired.
- CORS scoped to preview host + http://localhost:3000.
- Brand: "App N SaaS Builder".
- GitHub OAuth (public_repo), AES-256 Fernet-encrypted tokens, disconnect endpoint.
- Projects: full CRUD + repo picker + dashboard grid of ProjectCard.
- AI scoring via Claude Haiku 4.5 (Emergent LLM key), structured JSON.
- Polish: 12-week sparkline, CI badge, live URL, weighted next-steps checklist
  with server-side completion %, re-scan preserves done-flags for identical steps.
- **Score history**: `GET /api/projects/{id}/scores` + SVG line chart on
  ProjectDetail (renders once ≥2 scans exist).
- Stripe billing (P5): $30/mo Pro, 3-repo free-tier cap (402 with
  `code: 'free_tier_limit_reached'`), Managed Payments (tax_mode='full'),
  Settings → Billing card, /payment/success + /payment/cancel pages.
- Top Movers widget: `GET /api/movers`, dashboard strip above the grid.
- **Background jobs (P6, in-process APScheduler)**:
  - Weekly Progress Digest — Mondays 15:00 UTC.
  - Nightly re-scan of projects whose latest score is >24h old — 03:00 UTC.
  - `DISABLE_SCHEDULER=1` env kills both for CI.
- **Progress Digest email**: `_build_digest_for_user` computes portfolio avg,
  7-day movers (2+ scores, non-zero delta), shipped-steps-this-week; renders
  dark-theme HTML + plaintext. Endpoints:
  - `GET /api/preferences` / `PATCH /api/preferences` — toggle
    `weekly_digest_enabled` (default true).
  - `GET /api/digest/preview` — preview + payload.
  - `POST /api/digest/send-test` — sends the digest to the caller's own email
    (useful for verifying Resend domain).
  - Settings → Weekly Digest card with switch + "Send me a preview now" button.
- **Resend from-domain**: `RESEND_FROM_DOMAIN` env; when set, sender becomes
  `no-reply@<domain>` (fallback keeps `onboarding@resend.dev` for testing).
- Testing agent iterations: 1–8, all green (last: 74/74 backend + 100% UI).

## Backlog / next
- P2: Private-repo scope-upgrade flow (deferred per PF-1).
- P2: Password strength meter, reveal-password toggle.
- P3: Session list + per-device revoke in Settings.
- **P3: Verify a real Resend sending domain** — user must add DNS records at
  `resend.com/domains`, then set `RESEND_FROM_DOMAIN=<verified-domain>` in
  backend/.env and restart. This unlocks digest + reset emails to ALL recipients.
- P6: Async /scan endpoint (return 202 + scan_id, client polls). Nightly cron
  already covers stale re-scans.
- P6: Score-history chart on projects with real cadence data — already shipped,
  needs projects with 2+ scans to render.
- P6: Rate-limit + brief lockout on `/api/auth/login` (credential-stuffing).
- P7 code-review items: split server.py into routers (auth/projects/billing/digest);
  add dispatcher lock to APScheduler jobs before scaling >1 uvicorn worker; wrap
  `resend.Emails.send` with `asyncio.wait_for(..., timeout=15)`.
