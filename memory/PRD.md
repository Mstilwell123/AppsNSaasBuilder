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
- Login rate-limit: 5 failed attempts per email in 15 min → 429.
- Settings page: profile, password, billing, weekly digest — all data-testids.
- Login page + Google fallback + /forgot-password + /reset-password + /register.
- CORS scoped. Brand: "App N SaaS Builder".
- GitHub OAuth (public_repo), AES-256 Fernet-encrypted tokens. Projects CRUD.
- AI scoring via Claude Haiku 4.5. Async /scan + `GET /api/scans/{id}` polling.
- Polish: 12-week sparkline, CI badge, live URL, weighted next-steps checklist,
  done-flag preservation on re-scan, streak badge (flame chip when ≥2 consecutive
  improving scans).
- Score history: `GET /api/projects/{id}/scores` + SVG line chart.
- Top Movers widget: `GET /api/movers`.
- **Billing v2 (this session)** — plan catalog + trials:
  - PLANS constant: `solo` ($29/8 builds), `team` ($49/32), `agency` ($149/200),
    `white_label` (contact_only).
  - Stripe catalog: `appnsaas_{solo,team,agency}_monthly` lookup_keys.
    `pro_monthly` deactivated.
  - `GET /api/billing/plans` — public, powers pricing page.
  - `GET /api/billing/subscription` — authed, returns
    `{plan_key, source, plan_name, active_builds_limit, tracked_projects,
    trial_ends_at, current_period_end, cancel_at_period_end}`.
  - `POST /api/billing/checkout` now takes `{plan_key}` and dispatches by
    lookup_key. white_label + unknown → 400.
  - **7-day auto-trial on Solo** at register (no card required). `trial_started_at`
    and `trial_ends_at` fields on user doc.
  - Plan-aware build limit: 402 `code:'build_limit_reached'` (with `limit`,
    `plan_key`) OR 402 `code:'trial_expired'`.
- Background jobs (APScheduler in-process): Mon 15:00 UTC weekly digest,
  03:00 UTC nightly re-scan of projects >24h stale.
- Weekly Progress Digest email + opt-out + preview + send-test endpoints.
- Testing agent iterations 1–10, all green (last: 106/106 backend).

## Backlog / next
- **Frontend billing v2 (highest priority — pairs with this backend work):**
  1. New public `/pricing` page consuming `GET /api/billing/plans` with 4 cards
     (Solo/Team/Agency + White Label contact-sales).
  2. `BillingProvider` context + `useBilling()` hook + `guard()` helper.
  3. Rewrite `BillingCard.jsx` to consume `/billing/subscription` shape
     (plan_key, source, trial_ends_at). Show trial days remaining + upgrade CTA.
  4. `UpgradeModal` when `POST /api/projects` returns 402 (both
     `build_limit_reached` and `trial_expired` codes).
  5. `/billing/success` polling rewrite — call `/api/billing/sync` after payment.
- **Nightly cron: trial lock** — mark trials past `trial_ends_at` without a
  billing row so users are prompted to upgrade.
- **Router split (deferred)** — server.py is now 1,995 lines. Extract
  auth/projects/billing/digest routers in a dedicated session.
- Stale-scan reaper (mark scans still `running` after 5 min as error).
- Wrap `resend.Emails.send` in `asyncio.wait_for(..., timeout=15)`.
- Remove vestigial `STRIPE_PRO_LOOKUP_KEY` / `FREE_TIER_PROJECT_LIMIT` env vars.
- Private-repo scope-upgrade flow (deferred per PF-1).
- Session list + per-device revoke in Settings.
- Verify a real Resend sending domain (user-side action).
