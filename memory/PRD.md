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
- Billing v2 backend — plan catalog + trials:
  - PLANS constant: `solo` ($29/8 builds), `team` ($49/32), `agency` ($149/200),
    `white_label` (contact_only).
  - Stripe catalog: `appnsaas_{solo,team,agency}_monthly` lookup_keys.
  - `GET /api/billing/plans` — public, powers pricing page.
  - `GET /api/billing/subscription` — authed, returns `{plan_key, source,
    plan_name, active_builds_limit, tracked_projects, trial_ends_at,
    current_period_end, cancel_at_period_end}`.
  - `POST /api/billing/checkout` takes `{plan_key}`; white_label + unknown → 400.
  - 7-day auto-trial on Solo at register (no card required).
  - Plan-aware build limit: 402 `code:'build_limit_reached'` OR `'trial_expired'`.
- Background jobs (APScheduler in-process): Mon 15:00 UTC weekly digest,
  03:00 UTC nightly re-scan, **04:00 UTC nightly trial-lock (`_job_lock_expired_trials`
  sets `locked_at` on users past `trial_ends_at` with no active subscription;
  idempotent, skips active-Stripe users)**.
- Weekly Progress Digest email + opt-out + preview + send-test endpoints.
- **Billing v2 frontend (2026-02):**
  - `/app/frontend/src/lib/billing.jsx` — `BillingProvider`, `useBilling()` hook,
    `guard()` helper, `daysLeft()` util.
  - `/pricing` page (public) — 4-card grid with "Popular" on Team and "Current"
    ring/badge on caller's active plan.
  - `UpgradeModal` — triggered by 402 from `POST /api/projects` in RepoPicker.
  - `BillingCard` rewritten for `/billing/subscription` shape.
  - `LockedGate` in App.js — trial-expired users are redirected to /pricing
    from every protected route.
- **Shipped-this-week badge (2026-02):**
  - `GET /api/activity/weekly` returns
    `{shipped_this_week, threshold:3, window_days:7}`.
  - `next_steps.completed_at` stamped on done→true (first time), unset on
    done→false. Preserved across scans and nightly rescans via
    `completed_at_map` keyed on step text.
  - `ShippedBadge` component in Dashboard header — visible when
    `shipped_this_week ≥ 3`, hidden otherwise. Emerald rocket-badge design.
- Testing agent iterations 1–12, all green (last: 7/7 new backend +
  4/4 frontend cases for the badge; full billing v2 flow verified in iter_11).

## Backlog / next
- **P1** — "Trial ending" banner at top of the app when `trial_ends_at` within
  3 days, with "Choose your plan" button (currently only surfaced on Settings
  and /pricing).
- **BillingProvider refresh semantics** — expose `refresh()` from `useBilling`
  and call it on portal/checkout return; currently reruns only on `user` change.
- **checkout metadata bug** (carry-over from iter_10 review) — Stripe session
  metadata still passes `STRIPE_PRO_LOOKUP_KEY`; should use `plan['lookup_key']`.
- **Router split (P2)** — server.py is now ~2,023 lines. Extract
  auth/projects/billing/digest routers.
- `_job_lock_expired_trials` locked_at filter: switch `{$in:[None,""]}` to
  explicit `$or:[{$exists:false},{null}]` for intent clarity.
- FastAPI `@app.on_event('startup'/'shutdown')` deprecated — migrate to lifespan.
- Stale-scan reaper (mark scans still `running` after 5 min as error).
- Wrap `resend.Emails.send` in `asyncio.wait_for(..., timeout=15)`.
- Remove vestigial `STRIPE_PRO_LOOKUP_KEY` / `FREE_TIER_PROJECT_LIMIT` env vars.
- Private-repo scope-upgrade flow (deferred per PF-1).
- Session list + per-device revoke in Settings.
- Verify a real Resend sending domain (user-side action).
- `ProjectDetail.jsx` decomposition (>300 lines) — flagged repeatedly by analyzer.
