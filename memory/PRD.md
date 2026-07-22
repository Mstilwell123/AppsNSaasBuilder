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
- **Forgot password + reset password** via Resend (30-min single-use tokens).
- Settings page (profile + password + billing) with data-testids and inline errors.
- Login page with email/password form + Google as secondary; `/forgot-password`
  and `/reset-password` pages fully wired.
- **CORS tightened**: `CORS_ORIGINS` scoped to preview host + `http://localhost:3000`.
- **Brand rebrand**: "App N SaaS Builder" throughout header, login, emails.
- **GitHub OAuth (P2)**: connect, callback, repos, disconnect. AES-256 encrypted tokens.
- **Projects (P2)**: full CRUD + repo picker + dashboard grid of ProjectCard.
- **AI scoring (P3)**: Claude Haiku 4.5 via Emergent LLM key. Structured JSON output.
- **Polish (P4)**: 12-week sparkline, CI badge, live URL, weighted next-steps checklist
  with server-side completion %, re-scan carries over done-flags for identical steps.
- **Stripe billing (P5)**: $30/mo Pro plan, 3-repo free-tier cap (HTTP 402 with
  `code: "free_tier_limit_reached"`). Endpoints: `/api/billing/status`, `/checkout`,
  `/portal`, `/api/payments/status/{sid}`, `/api/stripe/webhook`. Tax mode = full
  (Stripe Managed Payments). Settings → Billing card. `/payment/success` polling +
  `/payment/cancel` pages.
- **Top Movers widget**: `GET /api/movers` returns projects with 2+ scores sorted by
  absolute delta desc; zero-delta and single-score excluded. Dashboard strip above
  the grid with up/down chips.
- Testing agent 7× iterations, all green (58/58 backend + 9/9 UI at latest).
- `/app/auth_testing.md` + `/app/memory/test_credentials.md` current.

## Backlog / next
- P1: Sign-up route (email + password) — REGISTER test IDs already declared, no page yet.
- P2: Private-repo scope-upgrade flow (deferred per PF-1).
- P2: Password strength meter, reveal-password toggle.
- P3: Session list + per-device revoke in Settings.
- P3: Verify a custom Resend domain to unlock reset emails to arbitrary recipients.
- P6: Background scan queue + cron (currently manual `/scan`).
- P6: Score history chart (scores collection already retains history).
- P6: Rate-limit `/api/auth/login` for credential-stuffing hardening.
- P7: Frontend Playwright coverage for the TopMovers UI (backend 100% covered;
  main-agent screenshot verified up/down chips render correctly).
