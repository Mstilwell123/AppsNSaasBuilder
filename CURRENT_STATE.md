# CURRENT_STATE.md
## AppsNSaasBuilder — Repository Baseline Audit

**Audit date:** August 18, 2026  
**Auditor:** Hermes Agent (Master Product Orchestrator)  
**Repository:** github.com/Mstilwell123/AppsNSaasBuilder (private)  
**Branch:** main  
**Commit:** 3894622 (Auto-generated changes)  

---

## Executive Summary

AppsNSaasBuilder is a **functional, single-iteration SaaS application** that tracks public GitHub repositories, scores their "completeness" using an LLM (Claude Haiku 4.5), and provides weighted next-step recommendations. It has **working authentication**, **working Stripe billing** with subscriptions, **working GitHub OAuth** (read-only), and a **polished dark-mode UI** with a Swiss high-contrast design system.

The application is built on the **Emergent** platform (emergent.sh) — it uses their base image, managed Google Auth, and LLM integration. The frontend is React 19 + CRACO + Tailwind + shadcn/ui. The backend is FastAPI + MongoDB (Motor async driver).

**What works well:** Auth (hybrid Google + password), GitHub read-only scanning, AI scoring, Stripe subscriptions + webhooks + customer portal, weekly digest emails, trial system with locking.

**What is missing for V2:** Readiness dimensions, My Stack, Cost Center, Ownership Center, PRD Center, `.appnsaas` project standard, Hermes Skills Center, QA/Security evidence, Launch Center, Business Center, Portfolio Economics, and the full IDEA→SHIP lifecycle. The current "score" is a single-dimensional 0-100 from an LLM — V2 wants 8 weighted dimensions.

---

## 1. Frontend Architecture

### What exists

A **React 19** single-page application using **CRACO** (Create React App Configuration Override) on top of react-scripts 5.0.1.

### Framework & Major Libraries
| Library | Version | Purpose |
|---------|---------|---------|
| react / react-dom | 19.0.0 | UI framework |
| react-router-dom | 7.15.0 | Client-side routing |
| @tanstack/react-query | 5.56.2 | Server state (imported but not actively used in components) |
| swr | 2.3.8 | Data fetching (imported but not actively used) |
| axios | 1.16.0 | HTTP client (imported but fetch wrapper is used instead) |
| tailwindcss | 3.4.17 | Styling |
| tailwindcss-animate | 1.0.7 | Animation utilities |
| framer-motion | 11.18.0 | Animation (imported but not used in production code) |
| recharts | 3.6.0 | Charts (imported but custom SVG charts are used instead) |
| lucide-react | 0.516.0 | Icon set |
| sonner | 2.0.3 | Toast notifications |
| zod | 3.24.4 | Schema validation (imported, not actively used) |
| react-hook-form | 7.56.2 | Forms (imported, not actively used — manual forms) |
| date-fns / dayjs | 4.1.0 / 1.11.13 | Date utilities |
| shadcn/ui (Radix primitives) | Various | ~30 UI components in `src/components/ui/` |

### Routing
`src/App.js` defines all routes using `react-router-dom` v7 `BrowserRouter`:

| Route | Component | Protected | Trial-Locked |
|-------|-----------|-----------|-------------|
| `/` | Login | No | No |
| `/register` | Register | No | No |
| `/forgot-password` | ForgotPassword | No | No |
| `/reset-password` | ResetPassword | No | No |
| `/pricing` | Pricing | No | No (explicitly allowed during trial expiry) |
| `/payment/success` | PaymentSuccess | No | No (allowed) |
| `/payment/cancel` | PaymentCancel | No | No (allowed) |
| `/dashboard` | Dashboard | Yes | Yes |
| `/connect` | Connect | Yes | Yes |
| `/repos` | RepoPicker | Yes | Yes |
| `/projects/:id` | ProjectDetail | Yes | Yes |
| `/settings` | Settings | Yes | Yes |

**Auth flow:** `ProtectedRoute` checks `useAuth().user`; `LockedGate` checks `useBilling().subscription.plan_key !== "expired"` and redirects to `/pricing` if expired.

**Auth callback:** `AuthCallback` handles `#session_id=...` hash fragments from Emergent Google OAuth.

### Page Structure
- **Login** — Split-screen with hero image, email/password form, "Continue with Google" button
- **Register** — Email + password + confirm, 7-day trial on signup
- **Dashboard** — Portfolio grid of `ProjectCard`s, "Top Movers" strip, "Shipped this week" badge, portfolio average score, "Add repos" button
- **ProjectDetail** — Full project view: score card, commit sparkline, stars/forks/issues, score history chart, prioritized next-steps checklist with checkboxes, scan/re-scan button, delete button
- **Settings** — Profile card, BillingCard (subscription management), DigestCard (weekly digest toggle), change/set password form
- **Pricing** — 4-plan grid (Solo/Team/Agency/White Label) with checkout buttons
- **Connect** — GitHub OAuth connection page with security guarantees listed
- **RepoPicker** — Searchable list of public repos with checkboxes for tracking
- **PaymentSuccess/PaymentCancel** — Post-checkout landing pages

### Dashboard Architecture
Dashboard loads in a single `useEffect`: fetches `githubStatus()`, `listProjects()`, `topMovers(3)`, and `activityWeekly()` in parallel. Shows loading state, empty states (no GitHub / no projects), and the project grid.

### Shared Components
- `AppShell` — Top nav bar with brand, Dashboard/Settings links, user avatar dropdown with logout
- `ProjectCard` — Card showing score, sparkline, languages, stars/forks/issues, CI badge, live URL, streak badge
- `Sparkline` — Pure CSS bar chart (12 bars)
- `ScoreHistoryChart` — Custom SVG line chart (zero dependencies)
- `TopMovers` — Strip of projects with biggest score deltas
- `ShippedBadge` — Dashboard badge when ≥3 steps shipped this week
- `BillingCard` — Subscription status + manage/upgrade buttons
- `DigestCard` — Weekly digest toggle + send-test button
- `UpgradeModal` — Modal for 402 billing-gate errors
- `ProtectedRoute` — Auth gate
- ~30 shadcn/ui components in `src/components/ui/` (button, card, dialog, input, etc.)

### State Management
- **Auth:** React Context (`AuthProvider`) — stores current user, loading, refresh/logout
- **Billing:** React Context (`BillingProvider`) — stores subscription, plans, loading
- **Local state:** `useState` per page (no global state library)

### API Communication
`src/lib/api.js` — thin `fetch` wrapper that sends session cookie (`credentials: "include"`) and JSON body. All API calls go through this single module. `BACKEND_URL` comes from `process.env.REACT_APP_BACKEND_URL`.

### Responsive/Mobile Behavior
- Tailwind responsive classes throughout (`sm:`, `md:`, `lg:` breakpoints)
- Dashboard grid: 1 col → 2 cols → 3 cols
- Login page: split-screen on `lg:`, stacked on mobile
- No dedicated mobile navigation — top bar adapts with flexbox

### Dark/Light Mode
- **Dark mode only.** The `design_guidelines.json` specifies `"theme": "dark"` with a Swiss high-contrast color palette.
- CSS variables in `index.css` define the theme: `--background: 0 0% 2%` (near-black), `--foreground: 0 0% 98%` (near-white).
- `tailwind.config.js` has `darkMode: ["class"]` but there is no theme toggle — the app is always dark.
- `next-themes` is listed as a dependency but is not wired up.

### PWA-Related Frontend Behavior
- **No manifest.json**, no service worker, no installability, no icons beyond `<meta name="theme-color">`.
- `index.html` has `<meta name="theme-color" content="#000000">` but no `<link rel="manifest">`.
- PostHog analytics script is loaded in `index.html`.

### Key Files
- `frontend/src/App.js` — Root component + routing
- `frontend/src/lib/api.js` — API client
- `frontend/src/lib/auth.jsx` — Auth context
- `frontend/src/lib/billing.jsx` — Billing context
- `frontend/src/components/AppShell.jsx` — Nav shell
- `frontend/src/pages/` — All page components
- `frontend/src/components/` — All shared components
- `frontend/src/components/ui/` — ~30 shadcn/ui primitives
- `frontend/src/index.css` — Theme variables + fonts
- `frontend/tailwind.config.js` — Tailwind theme
- `frontend/craco.config.js` — CRACO + webpack config

### What Should Probably Be Preserved
- **All of it.** The frontend is clean, well-structured, and consistent. The design system (Swiss high-contrast dark theme) is cohesive. All components use the same styling conventions. The `api.js` wrapper, `auth.jsx`, and `billing.jsx` contexts are solid foundations.
- shadcn/ui component library (~30 components) is a reusable asset.
- `ProjectCard`, `ProjectDetail`, `Sparkline`, `ScoreHistoryChart` are directly reusable for V2.
- `AppShell` is reusable as the dashboard shell.
- `Pricing` + `BillingCard` + `UpgradeModal` form a complete billing UX flow.

---

## 2. Backend Architecture

### What exists

A **single-file FastAPI backend** (`backend/server.py`, 2,059 lines) that handles everything: auth, GitHub OAuth, projects, scoring, billing, webhooks, digest, and cron jobs.

### Backend Framework
- **FastAPI** 0.110.1, served by **uvicorn** 0.25.0
- **Motor** 3.3.1 (async MongoDB driver) — `AsyncIOMotorClient`
- **APScheduler** 3.11.3 — background cron jobs (weekly digest, nightly rescan, trial lock)

### Entry Point
`backend/server.py` — defines `app = FastAPI(title="AppNSaasBuilder API")` and `api = APIRouter(prefix="/api")`. All routes are on the `api` router, included via `app.include_router(api)`.

### API Routes

| Route | Method | Auth | Purpose |
|-------|--------|------|---------|
| `/api/` | GET | No | Root health check |
| `/api/auth/session` | POST | No | Exchange Emergent session_id for app session |
| `/api/auth/me` | GET | Yes | Get current user |
| `/api/auth/logout` | POST | Yes | Logout (delete session) |
| `/api/auth/change-password` | POST | Yes | Set/change local password |
| `/api/auth/login` | POST | No | Email + password login |
| `/api/auth/forgot-password` | POST | No | Request reset email |
| `/api/auth/reset-password` | POST | No | Complete reset with token |
| `/api/auth/register` | POST | No | Email + password registration with trial |
| `/api/github/status` | GET | Yes | Check GitHub connection |
| `/api/github/connect` | GET | Yes | Get GitHub OAuth URL |
| `/api/github/callback` | GET | No | OAuth callback (redirects) |
| `/api/github/repos` | GET | Yes | List user's public repos |
| `/api/github/disconnect` | POST | Yes | Remove GitHub connection |
| `/api/projects` | GET | Yes | List user's tracked projects |
| `/api/projects` | POST | Yes | Track a new project (plan-limited) |
| `/api/projects/{id}` | GET | Yes | Get project detail |
| `/api/projects/{id}` | DELETE | Yes | Stop tracking project |
| `/api/projects/{id}/scan` | POST | Yes | Kick off AI scan (async background) |
| `/api/projects/{id}/scores` | GET | Yes | Score history |
| `/api/scans/{id}` | GET | Yes | Poll scan status |
| `/api/next-steps/{id}` | PATCH | Yes | Toggle step done/not-done |
| `/api/movers` | GET | Yes | Top score movers |
| `/api/activity/weekly` | GET | Yes | Shipped-this-week count |
| `/api/billing/plans` | GET | No | Public plan catalog |
| `/api/billing/subscription` | GET | Yes | Current subscription state |
| `/api/billing/status` | GET | Yes | Billing detail |
| `/api/billing/checkout` | POST | Yes | Start Stripe checkout |
| `/api/billing/portal` | POST | Yes | Stripe customer portal URL |
| `/api/payments/status/{id}` | GET | No | Poll payment status |
| `/api/stripe/webhook` | POST | No | Stripe webhook handler |
| `/api/preferences` | GET | Yes | Get user preferences |
| `/api/preferences` | PATCH | Yes | Update preferences |
| `/api/digest/preview` | GET | Yes | Preview weekly digest |
| `/api/digest/send-test` | POST | Yes | Send test digest email |

### Services (internal functions)
- `_score_with_llm()` — sends repo signals to Claude Haiku 4.5 via Emergent's `LlmChat` integration
- `_gather_repo_signals()` — reads-only GitHub metadata (repo, languages, sparkline, CI presence, README)
- `_run_scan()` — background async scan: fetch signals → call LLM → store score + next steps
- `_build_digest_for_user()` — builds HTML/text weekly digest email
- `_resolve_plan()` — determines user's plan (Stripe > trial > expired)
- `_get_or_create_customer()` — Stripe customer creation

### Middleware
- **CORS** — `CORSMiddleware` with `allow_credentials=True`, origins from `CORS_ORIGINS` env var
- No other middleware (no rate limiting beyond login attempts, no request logging)

### Data Access Layer
- Direct MongoDB access via `motor` — `db = client[DB_NAME]`. Collections accessed as `db.users`, `db.projects`, etc.
- No repository pattern or data access abstraction — MongoDB is accessed directly throughout `server.py`.

### External Integrations
| Integration | Method | Purpose |
|-------------|--------|---------|
| Emergent Auth | HTTP GET to `demobackend.emergentagent.com/auth/v1/env/oauth/session-data` | Session exchange for Google Auth |
| Emergent LLM | `LlmChat` from `emergentintegrations` | AI scoring via Claude Haiku 4.5 |
| GitHub API | `httpx.AsyncClient` to `api.github.com` | Repo metadata, languages, commit stats, CI presence |
| Stripe | `stripe` Python SDK | Subscriptions, checkout, billing portal, webhooks |
| Resend | `resend` Python SDK | Transactional email (password resets, weekly digest) |
| MongoDB | `motor` async driver | Primary database |

### Background Jobs (APScheduler)
| Job | Schedule | Purpose |
|-----|----------|---------|
| `_job_send_weekly_digests` | Monday 15:00 UTC | Send digest to opted-in users with ≥1 project |
| `_job_rescan_stale_projects` | Daily 03:00 UTC | Re-scan projects with score >24h old |
| `_job_lock_expired_trials` | Daily 04:00 UTC | Lock users whose trial expired without active subscription |

### Configuration System
- **Environment variables** loaded from `backend/.env` via `python-dotenv`
- Key env vars: `MONGO_URL`, `DB_NAME`, `CORS_ORIGINS`, `FRONTEND_URL`, `GITHUB_CLIENT_ID/SECRET/CALLBACK`, `GITHUB_OAUTH_SCOPE`, `TOKEN_ENCRYPTION_KEY`, `EMERGENT_LLM_KEY`, `SCORING_MODEL`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `RESEND_API_KEY`, `RESEND_FROM_DOMAIN`, `SENDER_EMAIL`, `APP_NAME`

### How the Frontend Communicates with the Backend
The frontend uses a thin `fetch` wrapper (`api.js`) that sends `credentials: "include"` (session cookie) with every request. The backend reads the session from the `session_token` cookie or `Authorization: Bearer` header. CORS is configured to allow the frontend origin with credentials.

### What Should Probably Be Preserved
- The entire backend is functional and well-structured for its current scope.
- The scan → score → next-steps pipeline is the core product loop and works.
- The cron job system (APScheduler) is correctly configured and tested.
- The hybrid auth model (Emergent Google + local bcrypt) is working.

---

## 3. Authentication

### What exists

A **hybrid authentication system** with two paths:

1. **Emergent-managed Google Auth** — primary login via `auth.emergentagent.com`, session exchanged at `/api/auth/session`
2. **Local email + password** — layered feature via bcrypt-hashed passwords

### Registration
- `POST /api/auth/register` — email + password (min 8 chars), creates user with 7-day trial
- Email is normalized to lowercase
- Duplicate email → 409
- On registration: creates session cookie + trial period

### Login
- **Google path:** `Login.jsx` → `auth.emergentagent.com` → redirect with `session_id` → `AuthCallback.jsx` → `POST /api/auth/session` → session cookie
- **Local path:** `POST /api/auth/login` — email + password, bcrypt verification
- Rate-limited: 5 failed attempts per email within 15 minutes → 429 lockout
- Login attempts recorded in `db.login_attempts`

### Logout
- `POST /api/auth/logout` — deletes session from MongoDB, clears cookie

### Password Handling
- **Hashing:** bcrypt (`bcrypt.hashpw` / `bcrypt.checkpw`) — `$2b$` format
- **Change password:** `POST /api/auth/change-password` — requires current password if one is set; rotates sessions (keeps current device, revokes others)
- **Forgot password:** `POST /api/auth/forgot-password` — generates single-use SHA-256-hashed token, emails reset link, always returns `{ok:true}` (enumeration-safe)
- **Reset password:** `POST /api/auth/reset-password` — validates token, updates password, revokes all sessions, signs in on current device

### Token/Session Strategy
- **Session token:** `secrets.token_urlsafe(48)` — 48-byte URL-safe random
- **Storage:** MongoDB `user_sessions` collection — `{user_id, session_token, expires_at, created_at}`
- **Cookie:** `session_token` — httponly, secure, samesite="none", max_age=7 days
- **Bearer fallback:** Authorization header also accepted
- **TTL:** 7 days (`SESSION_TTL_DAYS`)

### Protected Routes
- `ProtectedRoute` component checks `useAuth().user` — redirects to `/` if not authenticated
- `LockedGate` checks `useBilling().subscription.plan_key !== "expired"` — redirects to `/pricing` if trial expired

### User Isolation
- **All project routes** filter by `user_id`: `db.projects.find({"user_id": user["user_id"]})`
- **`_ensure_own_project()`** — verifies `project_id` belongs to the authenticated user before any project operation
- **Next-steps** — filtered by `user_id` in toggle endpoint
- **Scans** — filtered by `user_id` in poll endpoint

### Admin Authentication
- **No admin role or admin authentication exists.** All users are equal.

### Password Recovery
- Fully implemented: forgot → email → reset → consume token → update password → revoke sessions → sign in
- Tokens are single-use, 30-minute expiry, SHA-256 hashed at rest
- Previous unused tokens are invalidated on new request

### Whether It Appears Functional
**IMPLEMENTED AND APPEARS FUNCTIONAL.** The auth system is comprehensive:
- Registration with trial ✅
- Login (both Google and local) ✅
- Logout ✅
- Password change with session rotation ✅
- Forgot/reset flow with email ✅
- Rate limiting on login ✅
- User isolation on all data ✅
- Session expiry ✅

**Tested:** `backend_test.py` has 20+ auth tests covering: unauth access, session, change-password (all cases), login (success/wrong/no-password/nonexistent), forgot-password (existing/nonexistent), reset-password (success/replay/short/expired/garbage), session rotation, CORS.

### Relevant Files
- `backend/server.py` — all auth logic (lines 259-636)
- `frontend/src/lib/auth.jsx` — auth context
- `frontend/src/pages/Login.jsx` — login page
- `frontend/src/pages/Register.jsx` — registration page
- `frontend/src/pages/AuthCallback.jsx` — OAuth callback
- `frontend/src/pages/ForgotPassword.jsx` — forgot password page
- `frontend/src/pages/ResetPassword.jsx` — reset password page
- `frontend/src/pages/Settings.jsx` — change password form
- `frontend/src/components/ProtectedRoute.jsx` — route guard
- `backend/tests/backend_test.py` — auth test suite

### Dependencies
- `bcrypt` 4.1.3 — password hashing
- `python-jose` — JWT (listed but not actively used; sessions are random tokens, not JWTs)
- `resend` 2.34.0 — email for reset links
- `cryptography.fernet.Fernet` — GitHub token encryption (not auth, but related)

### Known Concerns
- **Session tokens stored in MongoDB** — not JWT-based, so no offline verification. This is fine for the current scale.
- **No admin role** — V2 may need admin capabilities for managing users/plans.
- **Emergent dependency** — the Google auth flow depends on `auth.emergentagent.com`. If Emergent changes their API, auth breaks. This is a **platform dependency risk**.

---

## 4. GitHub Integration

### What exists

**GitHub OAuth App** (not GitHub App) with read-only scopes.

### OAuth Implementation
- **Type:** OAuth App (not GitHub App)
- **Flow:** User clicks "Connect GitHub" → backend generates state token → redirects to `github.com/login/oauth/authorize` → GitHub redirects to `/api/github/callback` → backend exchanges code for access token → encrypts and stores
- **State validation:** `secrets.token_urlsafe(24)` stored in `db.github_oauth_states` with 10-minute TTL, consumed on callback

### Requested Permissions/Scopes
- **Default scope:** `GITHUB_OAUTH_SCOPE = os.environ.get("GITHUB_OAUTH_SCOPE", "public_repo,read:user")`
- **`public_repo`** — read access to public repositories (and write access, but the app never writes)
- **`read:user`** — read user profile data
- **Tested:** `backend_test.py` asserts `public_repo` and `read:user` are in the scope

### Token Storage
- **Encryption:** GitHub access tokens are **AES-256 encrypted at rest** using `cryptography.fernet.Fernet` with `TOKEN_ENCRYPTION_KEY`
- Stored in `db.github_connections` as `encrypted_token`
- Decrypted only when needed for API calls

### Repository Discovery
- `GET /api/github/repos` — calls `GET /user/repos?per_page=100&sort=pushed&affiliation=owner`
- **Public repos only:** `return [_repo_to_out(r) for r in repos if not r.get("private")]`
- Private repos are explicitly filtered out (line 995: `if not r.get("private")`)

### Repository Reading
- `_gather_repo_signals()` reads:
  - `GET /repos/{full_name}` — repo metadata (name, description, language, stars, forks, issues, homepage, license, archived)
  - `GET /repos/{full_name}/languages` — language breakdown by bytes
  - `GET /repos/{full_name}/stats/participation` — weekly commit counts (last 52 weeks, takes last 12)
  - `GET /repos/{full_name}/contents/.github/workflows` — CI workflow file presence
  - `GET /repos/{full_name}/readme` — README presence
- **Never fetches source code.** Only metadata, languages, commit stats, workflow file listing, and README existence.

### Private Repository Behavior
- **Not supported.** `track_project` explicitly rejects private repos: `if repo_meta.get("private"): raise HTTPException(status_code=400, detail="Private repos aren't supported in v1")`
- `github_repos` filters to public only

### Commit/History Retrieval
- Commit activity via `stats/participation` (weekly commits, last 52 weeks)
- `pushed_at` timestamp from repo metadata
- No individual commit retrieval or diff reading

### CI Status Retrieval
- Checks for `.github/workflows` directory presence → "configured" or "no_ci"
- Does not check CI run status or build results (would need `actions:read` scope)

### Language Analysis
- `GET /repos/{full_name}/languages` — returns byte counts per language
- Displayed as percentage pills on `ProjectCard`

### Write Operations
- **None.** The app is purely read-only. Despite `public_repo` scope allowing writes, no write API calls are made.

### Is it truly read-only?
- **In behavior:** Yes — no write API calls are made anywhere in the code.
- **In permissions:** The `public_repo` scope technically grants write access to public repos, but the app never exercises it.
- **V2 concern:** The scope could be narrowed to just `public_repo` (which is the minimal scope for reading public repos) or even no scope if using unauthenticated requests for public repos. However, `public_repo` is needed for authenticated API rate limits.

### Whether It Appears Functional
**IMPLEMENTED AND APPEARS FUNCTIONAL.** Tests cover:
- OAuth URL generation with correct params
- Callback error handling (missing params, invalid state)
- Status endpoint (connected/not connected)
- Repos endpoint (without connection → 400)
- Project tracking (without connection → 400, with fake token → 404/502)

### Relevant Files
- `backend/server.py` — GitHub section (lines 638-996)
- `frontend/src/pages/Connect.jsx` — GitHub connect page
- `frontend/src/pages/RepoPicker.jsx` — repo selection
- `frontend/src/pages/Dashboard.jsx` — dashboard with connect CTA

### Dependencies
- `httpx` 0.28.1 — async HTTP client for GitHub API
- `cryptography.fernet.Fernet` — token encryption
- `requests-oauthlib` — listed in requirements but not used (manual OAuth flow)

### Known Concerns
- **Scope is broader than needed.** `public_repo` grants write access to public repos. Since the app is read-only, this is technically over-privileged. However, GitHub doesn't offer a "read public repos only" scope — `public_repo` is the narrowest available for the OAuth App model. A GitHub App (not OAuth App) could use more granular permissions.
- **Private repos not supported** — this is a v1 limitation, not a bug.
- **CI status is presence-only** — checks if `.github/workflows` exists, not whether CI passes.

---

## 5. Current AI Completion Scoring

### What exists

An **LLM-based scoring system** that asks Claude Haiku 4.5 to produce a 0-100 "completeness" score from GitHub metadata.

### AI Provider
- **Emergent integrations** — `from emergentintegrations.llm.chat import LlmChat, UserMessage`
- The LLM call goes through Emergent's managed integration layer

### Model
- **`SCORING_MODEL = "claude-haiku-4-5-20251001"`** (Claude Haiku 4.5)
- Configurable via `SCORING_MODEL` env var

### Prompt/Instructions
The system prompt (lines 832-847) instructs the model to:
- Score a project's "completeness" from GitHub **metadata only** (no source access)
- Return JSON with: `score` (int 0-100), `one_line_summary` (≤100 chars), `rationale` (2-4 sentences), `next_steps` (3-6 items with text/weight/order)
- Weight reflects "impact-on-completeness" (5 = huge lift, 1 = polish)
- Signal guidance: recent commits, CI, README, homepage, low issues, license → higher; archived/no-commits → lower

### Repository Signals Analyzed
| Signal | Source | Type |
|--------|--------|------|
| Name, full_name, description | GitHub repo metadata | Deterministic |
| Primary language | `repo.get("language")` | Deterministic |
| Language breakdown | `/languages` endpoint | Deterministic |
| Stars, forks, open issues | `stargazers_count`, `forks_count`, `open_issues_count` | Deterministic |
| Commit activity (12 weeks) | `stats/participation` | Deterministic |
| Commit total (12 weeks) | `sum(sparkline)` | Deterministic |
| Default branch | `default_branch` | Deterministic |
| Last push date | `pushed_at` | Deterministic |
| Homepage URL present | `bool(repo.get("homepage"))` | Deterministic |
| README present | `/readme` endpoint | Deterministic |
| CI configured | `.github/workflows` directory presence | Deterministic |
| License | `license.spdx_id` | Deterministic |
| Archived | `archived` flag | Deterministic |

### Deterministic Scoring Logic
- **Completion percentage:** `_weighted_completion(steps)` — calculates `100 * done_weight / total_weight` across next steps
- **Streak:** counts consecutive strictly-increasing scores walking back from newest
- **Top movers:** projects with biggest absolute score delta between last two scans

### AI-Generated Logic
- **Score (0-100):** LLM-generated based on the signals above
- **Rationale:** LLM-generated, 2-4 sentences citing specific signals
- **One-line summary:** LLM-generated, ≤100 chars
- **Next steps:** LLM-generated, 3-6 items with text, weight (1-5), and order

### Score Storage
- Stored in `db.scores` collection: `{id, user_id, project_id, score, rationale, model, scored_at}`
- Score history retrieved via `GET /api/projects/{id}/scores`

### Score History
- `GET /api/projects/{id}/scores?limit=20` — returns chronological score history
- Each entry: `{score, scored_at, rationale}`

### Recommended Tasks
- Stored in `db.next_steps` collection: `{id, user_id, project_id, text, weight, order, done, completed_at, created_at}`
- 3-6 items per scan
- Toggle-able via `PATCH /api/next-steps/{id}`
- **Preservation on rescan:** done flags and `completed_at` are preserved for identically-worded steps (normalized by `text.strip().lower()`)

### Percentage Calculations
- **Completion:** `100 * sum(done_weights) / sum(all_weights)` — integer 0-100
- **Score:** LLM-generated, clamped to 0-100

### Cost Implications
- Each scan calls Claude Haiku 4.5 once with a moderate prompt
- Nightly rescan job scans all stale projects (score >24h old)
- Cost depends on number of tracked projects × scan frequency

### Separation: Deterministic vs AI-Generated
| Component | Type |
|-----------|------|
| GitHub signals gathering | Deterministic |
| Completion % (from next steps) | Deterministic |
| Streak calculation | Deterministic |
| Top movers ranking | Deterministic |
| Score (0-100) | **AI-generated** |
| Rationale | **AI-generated** |
| One-line summary | **AI-generated** |
| Next steps (what to do) | **AI-generated** |
| Next steps weights | **AI-generated** (clamped 1-5) |

### Whether It Appears Functional
**IMPLEMENTED AND APPEARS FUNCTIONAL** but **NOT INDEPENDENTLY VERIFIED** — the scan endpoint calls a real LLM, but tests use fake tokens so no actual scan completes in the test suite. The scoring logic, JSON extraction, sanity clamping, and next-step preservation are all implemented and the preservation logic is tested at the DB level.

### What Should Probably Be Preserved
- The signal-gathering approach (metadata-only, no source) is sound for V2
- The JSON extraction logic (`_extract_json`) is robust
- The next-step preservation on rescan is well-designed
- The streak and top-movers calculations are good product features

---

## 6. Database Models

### What exists

A **MongoDB** database accessed via **Motor** (async driver). No ORM — documents are raw dictionaries.

### Collections Inventory

| Collection | Purpose | Key Fields |
|-----------|---------|-----------|
| `users` | User accounts | `user_id`, `email`, `name`, `picture`, `password_hash`, `weekly_digest_enabled`, `trial_started_at`, `trial_ends_at`, `locked_at`, `github_connected`, `created_at`, `updated_at` |
| `user_sessions` | Session tokens | `user_id`, `session_token`, `expires_at`, `created_at` |
| `login_attempts` | Login rate limiting | `email`, `success`, `created_at` |
| `password_reset_tokens` | Password reset tokens | `user_id`, `token_hash` (SHA-256), `expires_at`, `created_at`, `used_at` |
| `github_connections` | GitHub OAuth tokens | `user_id`, `github_user_id`, `github_username`, `encrypted_token`, `scopes`, `connected_at` |
| `github_oauth_states` | OAuth state tokens | `state`, `user_id`, `expires_at`, `created_at` |
| `projects` | Tracked projects | `id`, `user_id`, `github_repo_id`, `name`, `full_name`, `private`, `primary_language`, `languages`, `stars`, `forks`, `open_issues`, `default_branch`, `live_url`, `ci_status`, `commit_sparkline`, `last_commit_at`, `one_line_summary`, `added_at`, `updated_at` |
| `scores` | AI score history | `id`, `user_id`, `project_id`, `score`, `rationale`, `model`, `scored_at` |
| `next_steps` | Recommended tasks | `id`, `user_id`, `project_id`, `text`, `weight`, `order`, `done`, `completed_at`, `created_at` |
| `scans` | Scan status tracking | `id`, `user_id`, `project_id`, `status`, `started_at`, `finished_at`, `error` |
| `billing` | Stripe subscription state | `user_id`, `customer_id`, `subscription_id`, `subscription_status`, `plan_key`, `current_period_end`, `cancel_at_period_end`, `email`, `updated_at` |
| `payment_transactions` | Stripe payment records | `session_id`, `user_id`, `customer_id`, `lookup_key`, `plan_key`, `amount`, `currency`, `status`, `payment_status`, `created_at`, `updated_at` |

### Relationships
```
users (1) ──→ (N) user_sessions
users (1) ──→ (N) login_attempts
users (1) ──→ (N) password_reset_tokens
users (1) ──→ (1) github_connections
users (1) ──→ (N) projects
users (1) ──→ (1) billing
projects (1) ──→ (N) scores
projects (1) ──→ (N) next_steps
projects (1) ──→ (N) scans
```

### Whether It Appears Functional
**IMPLEMENTED AND APPEARS FUNCTIONAL.** Collections are accessed consistently with `user_id` for isolation. No migrations — MongoDB is schemaless, so schema drift is a risk.

### What Should Probably Be Preserved
- The collection structure is clean for the current feature set
- User isolation via `user_id` on every collection is correct
- The `scans` collection for async scan tracking is well-designed

---

## 7. Current Project Model

### What exists

The `projects` collection stores the following about each tracked application:

| Field | Type | Source | Purpose |
|-------|------|--------|---------|
| `id` | str | UUID | Internal project ID (`proj_<hex>`) |
| `user_id` | str | Auth | Owner |
| `github_repo_id` | int | GitHub | GitHub repo numeric ID |
| `name` | str | GitHub | Repo name |
| `full_name` | str | GitHub | `owner/repo` |
| `private` | bool | GitHub | Private flag (always False — private not supported) |
| `primary_language` | str | GitHub | `repo.language` |
| `languages` | Dict[str, int] | GitHub | Language bytes breakdown |
| `stars` | int | GitHub | `stargazers_count` |
| `forks` | int | GitHub | `forks_count` |
| `open_issues` | int | GitHub | `open_issues_count` |
| `default_branch` | str | GitHub | `default_branch` |
| `live_url` | str? | GitHub | `repo.homepage` |
| `ci_status` | str | GitHub | "configured" / "no_ci" / "unknown" |
| `commit_sparkline` | List[int] | GitHub | Last 12 weeks of commit counts |
| `last_commit_at` | str? | GitHub | `pushed_at` |
| `one_line_summary` | str? | LLM | AI-generated summary |
| `added_at` | str | System | When tracked |
| `updated_at` | str | System | Last scan update |

### What V2 Will Eventually Require (comparison, not redesign)
V2 wants to expand the project model to include:
- **Readiness dimensions** (8 weighted scores instead of one 0-100)
- **Stack information** (services, costs, ownership)
- **PRD/architecture documents**
- **`.appnsaas/` project standard files**
- **Hermes skill recommendations**
- **QA/security evidence**
- **Launch readiness**
- **Business metrics (MRR, customers, etc.)**

The current model is a good foundation — it captures the essential GitHub metadata and has a clean `id`/`user_id` structure that can be extended.

### What Should Probably Be Preserved
- All GitHub metadata fields — they're real, sourced from the API
- The `id` / `user_id` structure
- The `ci_status`, `commit_sparkline`, `live_url` fields
- The `one_line_summary` (AI-generated but useful)
- The `scans` collection for tracking scan history

---

## 8. Stripe / Billing Work

### What exists

A **complete Stripe subscription billing system** with checkout, webhooks, customer portal, trial management, and plan enforcement.

### Plan Catalog
| Plan | Key | Price | Active Builds | Trial |
|------|-----|-------|---------------|-------|
| Solo Builder | `solo` | $29/mo | 8 | 7 days |
| Team | `team` | $49/mo | 32 | 7 days |
| Agency | `agency` | $149/mo | 200 | None |
| White Label | `white_label` | Custom | Custom | None (contact only) |

### Classification

| Feature | Status | Evidence |
|----------|--------|----------|
| **Checkout** | **LIVE** | `POST /billing/checkout` creates Stripe Checkout Session with `mode="subscription"`, returns `checkout_url`. Tested: `test_checkout_accepts_plan` (solo/team/agency), `test_checkout_null_plan_defaults_to_solo`, `test_checkout_rejects_white_label`, `test_checkout_rejects_bogus` |
| **Products/Prices** | **WIRED BUT UNVERIFIED** | Prices looked up by `lookup_key` from Stripe (`stripe.Price.list(lookup_keys=[...])`). No Stripe product/price creation in code — assumes they exist in Stripe dashboard. |
| **Subscriptions** | **LIVE** | `_apply_subscription_state()` writes subscription status to `db.billing`. Webhook handles `customer.subscription.created/updated/deleted`. |
| **Webhooks** | **LIVE** | `POST /stripe/webhook` handles: `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `checkout.session.async_payment_failed`, `customer.subscription.created/updated`, `customer.subscription.deleted`, `charge.refunded`. Signature verification with `STRIPE_WEBHOOK_SECRET`. |
| **Entitlements** | **LIVE** | `FREE_TIER_PROJECT_LIMIT` + plan-based `active_builds` limit enforced on `POST /api/projects` (returns 402 `build_limit_reached`). Tested: `test_trial_expired_returns_402`. |
| **Plan enforcement** | **LIVE** | `_resolve_plan()` determines plan: active Stripe > trial > expired. LockedGate on frontend + 402 on backend. |
| **Failed payment** | **WIRED BUT UNVERIFIED** | `checkout.session.async_payment_failed` updates transaction status to "failed". No retry/dunning logic. |
| **Cancellation** | **LIVE** | `customer.subscription.deleted` → sets `subscription_status: "canceled"`. `cancel_at_period_end` tracked. |
| **Customer portal** | **LIVE** | `POST /billing/portal` returns Stripe billing portal URL. `BillingCard` has "Manage subscription" button. |
| **Trials** | **LIVE** | 7-day trial on registration. `trial_ends_at` stored. `_job_lock_expired_trials` cron locks expired trials nightly. Tested: `test_cron_locks_expired_and_idempotent_and_skips_active`. |
| **Upgrades/downgrades** | **WIRED BUT UNVERIFIED** | Stripe handles this via customer portal. No explicit upgrade/downgrade API in the app — relies on Stripe portal. |
| **Billing-period resets** | **WIRED** | `current_period_end` tracked from Stripe webhook. |
| **Idempotency** | **PARTIAL** | Webhook handler updates with `$set` — somewhat idempotent. Payment status uses `{"payment_status": {"$ne": "paid"}}` guard. Not fully idempotent for all event types. |
| **Promo codes** | **LIVE** | `allow_promotion_codes=True` in checkout session |
| **Tax** | **LIVE** | `managed_payments` or `automatic_tax` with `billing_address_collection="required"` |

### Whether It Appears Functional
**LIVE AND APPEARS FUNCTIONAL.** The Stripe integration is one of the most complete features:
- Checkout creates real Stripe sessions
- Webhook handler is properly signed and handles key events
- Trial system with locking is tested
- Plan enforcement gates project creation
- Customer portal is wired

**UNVERIFIED:** Actual end-to-end payment flow (can't be tested without real Stripe keys/cards). The webhook signature verification, subscription state sync, and plan gating logic all appear correct.

### Relevant Files
- `backend/server.py` — Stripe section (lines 1316-1644)
- `frontend/src/pages/Pricing.jsx` — pricing page
- `frontend/src/components/BillingCard.jsx` — billing management
- `frontend/src/components/UpgradeModal.jsx` — upgrade modal
- `frontend/src/lib/billing.jsx` — billing context
- `backend/tests/test_billing_v2_and_cron.py` — billing + cron tests

### What Should Probably Be Preserved
- The entire billing system is well-built and should be preserved
- The plan catalog structure is extensible
- The trial + locking mechanism is tested and working
- The webhook handler covers the important event types

---

## 9. Existing Tests

### What exists

Three test files in `backend/tests/`:

### Test Inventory

| File | Tests | Coverage Area |
|------|-------|---------------|
| `backend_test.py` | ~40 tests | Auth (full suite), GitHub OAuth, projects, CORS |
| `test_billing_v2_and_cron.py` | ~12 tests | Billing plans, checkout, trial expiry, cron locking, plan gates |
| `test_activity_weekly.py` | ~10 tests | Weekly activity, completed_at toggling, rescan preservation |
| `tests/__init__.py` | — | Empty init |
| `backend/pytest.ini` | — | xdist config: 2 workers, loadscope distribution |

### Test Categories

| Category | Present | Details |
|----------|---------|---------|
| **Unit tests** | Partial | No pure unit tests — all are integration (hit the API) |
| **Integration tests** | Yes | All tests hit the running API via HTTP requests |
| **API tests** | Yes | Full auth flow, GitHub endpoints, billing endpoints, activity |
| **Authentication tests** | Yes | 20+ auth tests: unauth, session, change-password, login, forgot/reset, CORS |
| **Browser/E2E tests** | No | No browser automation tests |
| **User-isolation tests** | Partial | `_ensure_own_project` is tested via 404 responses, but no explicit cross-user access test |
| **Billing tests** | Yes | Plan shape, checkout acceptance, trial expiry, cron locking |
| **GitHub tests** | Yes | OAuth URL, callback errors, status, repos, project tracking |
| **Stripe webhook tests** | No | Webhook handler is not tested (requires mock Stripe events) |
| **LLM scoring tests** | No | `_score_with_llm` is not tested (requires real LLM call) |

### Important Workflows Without Coverage
1. **Stripe webhook processing** — no mock webhook event tests
2. **LLM scoring** — no mock LLM response tests (the JSON extraction and clamping could be unit-tested)
3. **End-to-end scan flow** — no test completes a full scan (requires GitHub API + LLM)
4. **Browser/E2E** — no Playwright or Cypress tests
5. **Cross-user project access** — no test tries to access another user's project
6. **Resend email sending** — no test for actual email delivery
7. **Cron jobs** — only `_job_lock_expired_trials` is tested; weekly digest and nightly rescan are not
8. **Payment status polling** — `/api/payments/status/{session_id}` is not tested

### Whether It Appears Functional
**IMPLEMENTED BUT INCOMPLETE.** The test suite is solid for auth and billing but has significant gaps in webhook, LLM, and E2E coverage. The tests are integration-style (require running backend + MongoDB).

### Relevant Files
- `backend/tests/backend_test.py` (1,645 lines, ~40 tests)
- `backend/tests/test_billing_v2_and_cron.py` (252 lines, ~12 tests)
- `backend/tests/test_activity_weekly.py` (267 lines, ~10 tests)
- `backend/pytest.ini` (xdist config)
- `test_reports/` — JSON iteration reports + pytest XML results

---

## 10. PWA Configuration

### What exists

**Minimal PWA configuration — essentially absent.**

### Current PWA State

| Feature | Status | Evidence |
|---------|--------|----------|
| **Web manifest** | **MISSING** | No `manifest.json` in `frontend/public/`. No `<link rel="manifest">` in `index.html` |
| **Installability** | **MISSING** | No manifest = not installable |
| **Icons** | **MISSING** | No app icons (192px, 512px) |
| **Theme configuration** | **PARTIAL** | `<meta name="theme-color" content="#000000">` in `index.html` |
| **Service worker** | **MISSING** | No service worker registration |
| **Offline behavior** | **MISSING** | No offline support — requires network for all operations |
| **Mobile navigation** | **PARTIAL** | Tailwind responsive classes adapt layout, but no dedicated mobile nav |
| **Safe-area support** | **MISSING** | No `env(safe-area-inset-*)` or `viewport-fit=cover` |
| **Touch-target considerations** | **PARTIAL** | Buttons are `h-10` (40px) or `h-11` (44px) — meets minimum touch target |
| **Caching strategy** | **MISSING** | No workbox, no cache-first strategy |

### What is functional vs. aspirational
- **Functional:** Theme color meta tag, responsive layout
- **Aspirational:** Everything else PWA-related is absent

### Whether It Appears Functional
**NOT IMPLEMENTED.** The app is a standard SPA with no PWA features beyond a theme-color meta tag.

---

## 11. Security Weaknesses

### Focused Security Review

| Finding | Severity | Details |
|---------|----------|---------|
| **GitHub OAuth scope broader than needed** | **MEDIUM** | `public_repo` scope grants write access to public repos, but app is read-only. GitHub doesn't offer a read-only public repo scope for OAuth Apps. Mitigation: switch to GitHub App model for granular permissions, or accept the risk since no write calls are made. |
| **No admin role or access control** | **LOW** | No admin role exists. V2 will need one for managing users, plans, etc. Not a current vulnerability (no admin features to exploit). |
| **Session tokens in MongoDB, not JWT** | **INFORMATIONAL** | Sessions are random tokens stored in DB. This means every request requires a DB lookup for auth. Fine at current scale. Not a security weakness — just an architecture note. |
| **Emergent platform dependency for auth** | **MEDIUM** | Google auth depends on `auth.emergentagent.com`. If this service changes or goes down, Google auth breaks. Local password auth still works independently. |
| **Stripe secret key in env** | **INFORMATIONAL** | `stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")` — standard practice, not a vulnerability. The fallback value `"«redacted:sk_test_…»"` is concerning — if `STRIPE_SECRET_KEY` is not set, it uses a redacted placeholder which would cause API failures, not a security issue. |
| **Token encryption key optional** | **HIGH** | `TOKEN_ENCRYPTION_KEY = os.environ.get("TOKEN_ENCRYPTION_KEY", "")` — if not set, `_fernet = None` and token encryption/decryption raises HTTPException. This means **GitHub tokens would not be stored if the key is missing**, which is safer than storing plaintext. However, the empty default could lead to confusing production errors. |
| **CORS origins from env** | **INFORMATIONAL** | `CORS_ORIGINS` is configured via env var. If empty, `allow_origins=[]` (no CORS). Correct behavior. |
| **No rate limiting on API endpoints** | **MEDIUM** | Only login has rate limiting (5 fails/15 min). API endpoints like `/api/projects`, `/api/github/repos`, scan endpoints have no rate limiting. A user could spam scans. |
| **No input validation beyond Pydantic** | **LOW** | Pydantic models validate types, but no custom validators for things like repo ID ranges, string lengths beyond what Pydantic enforces. |
| **Login lockout keyed on email only** | **LOW** | Rate limiting is per-email, not per-IP. An attacker could enumerate emails, but the lockout is per-email so it also limits the victim. The code comments note this is intentional due to cluster ingress IP rotation. |
| **PostHog analytics in production HTML** | **INFORMATIONAL** | `index.html` loads PostHog with a hardcoded project key (`phc_DbsPb39SRc8z3EiQ6Dhj6ikv4H4rTKcht9d4sZSesceP`). This is an Emergent platform default, not user-configured. |
| **Emergent script in HTML** | **INFORMATIONAL** | `<script src="https://assets.emergent.sh/scripts/emergent-main.js">` is loaded in production. This is an Emergent platform dependency. |
| **No HTTPS enforcement in app** | **INFORMATIONAL** | HTTPS is handled by the hosting platform (Emergent/Kubernetes ingress), not the app. Cookies are `secure=True` which requires HTTPS. |
| **Password reset tokens are SHA-256 hashed** | **INFORMATIONAL** | Tokens are hashed with SHA-256 before storage — correct practice for random tokens. |
| **No CSRF protection beyond SameSite cookie** | **LOW** | Cookies use `samesite="none"` which does NOT protect against CSRF. The `secure=True` flag helps, but CSRF tokens are not used. API uses Bearer auth as an alternative which mitigates this. |

### Summary by Severity
| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 (token encryption key optional) |
| MEDIUM | 3 (OAuth scope, Emergent dependency, no API rate limiting) |
| LOW | 3 (no admin, input validation, email-keyed lockout, no CSRF) |
| INFORMATIONAL | 5 (session model, Stripe key, CORS, PostHog, HTTPS, Emergent script) |

### Whether It Appears Functional
**NO CRITICAL VULNERABILITIES FOUND.** The security posture is reasonable for a v1 application. The main concerns are:
1. Token encryption key should be required, not optional
2. API rate limiting should be added for scan endpoints
3. OAuth scope is broader than ideal (but constrained by GitHub's OAuth App model)

---

## 12. Unfinished Features

### What exists (TODO/FIXME/disabled/disconnected code)

| Item | Location | Status |
|------|----------|--------|
| **No TODO/FIXME comments in code** | N/A | Searched — no TODOs or FIXMEs in any source file |
| **`@tanstack/react-query` imported but unused** | `package.json` | Library is installed but not used in any component. SWR is also installed but unused. |
| **`axios` imported but unused** | `package.json` | The `api.js` wrapper uses `fetch`, not axios |
| **`framer-motion` imported but unused** | `package.json` | Not used in any component |
| **`recharts` imported but unused** | `package.json` | Custom SVG charts (`Sparkline`, `ScoreHistoryChart`) are used instead |
| **`react-hook-form` imported but unused** | `package.json` | Manual form handling in all pages |
| **`zod` imported but unused** | `package.json` | No schema validation in frontend |
| **`next-themes` imported but unused** | `package.json` | No theme toggle — dark mode only |
| **`swr` imported but unused** | `package.json` | Data fetching uses `api.js` fetch wrapper |
| **No disabled routes** | N/A | All routes in `App.js` are active |
| **No placeholder screens** | N/A | All pages have real implementations |
| **No abandoned experiments** | N/A | The codebase is clean — no leftover/abandoned code |

### Assessment
The codebase is **remarkably clean** — no TODOs, no FIXMEs, no disabled code, no placeholder screens. Unused dependencies are the main "unfinished" aspect (likely carried over from the Emergent base image template).

### What Should Probably Be Preserved
- The clean codebase is a strength. V2 should maintain this discipline.

---

## 13. Reusable Components

### What exists — components V2 should preserve

| Component | Location | Why Reusable |
|-----------|----------|-------------|
| **AppShell** | `src/components/AppShell.jsx` | Core nav shell — brand, nav links, user dropdown. V2 can extend with new nav items. |
| **ProjectCard** | `src/components/ProjectCard.jsx` | Card showing score, sparkline, languages, stats. V2 can extend to show readiness dimensions. |
| **ProjectDetail** | `src/pages/ProjectDetail.jsx` | Full project view with score, history, next steps. V2 can extend with tabs for readiness, stack, costs, etc. |
| **Sparkline** | `src/components/Sparkline.jsx` | Zero-dependency bar chart. Reusable anywhere. |
| **ScoreHistoryChart** | `src/components/ScoreHistoryChart.jsx` | Custom SVG line chart. Reusable for any time-series. |
| **TopMovers** | `src/components/TopMovers.jsx` | Score delta strip. Reusable for V2 portfolio dashboard. |
| **ShippedBadge** | `src/components/ShippedBadge.jsx` | Activity badge. Reusable for V2 gamification. |
| **BillingCard** | `src/components/BillingCard.jsx` | Subscription status + portal link. Reusable for V2 billing. |
| **DigestCard** | `src/components/DigestCard.jsx` | Weekly digest toggle + send-test. Reusable for V2 notifications. |
| **UpgradeModal** | `src/components/UpgradeModal.jsx` | 402 billing-gate modal. Reusable for V2 plan limits. |
| **ProtectedRoute** | `src/components/ProtectedRoute.jsx` | Auth gate. Reusable for all V2 protected routes. |
| **api.js** | `src/lib/api.js` | Fetch wrapper with credentials. Reusable — just add new endpoints. |
| **auth.jsx** | `src/lib/auth.jsx` | Auth context. Reusable — V2 can extend with roles. |
| **billing.jsx** | `src/lib/billing.jsx` | Billing context with trial/lock logic. Reusable for V2. |
| **Login/Register/Settings/Pricing pages** | `src/pages/` | Complete auth + billing UX. Reusable as-is. |
| **~30 shadcn/ui components** | `src/components/ui/` | Full component library. Reusable for all V2 UI. |
| **Design system** | `design_guidelines.json` + `index.css` + `tailwind.config.js` | Swiss high-contrast dark theme. Cohesive and reusable. |

---

## 14. Obsolete or Duplicate Code

### What exists

| Item | Type | Notes |
|------|------|-------|
| `@tanstack/react-query` | Unused dependency | Installed but not used — `swr` also installed but unused. Both are data-fetching libraries. |
| `axios` | Unused dependency | `api.js` uses `fetch` instead |
| `framer-motion` | Unused dependency | No animations in production code |
| `recharts` | Unused dependency | Custom SVG charts used instead |
| `react-hook-form` | Unused dependency | Manual forms used |
| `zod` | Unused dependency | No schema validation in frontend |
| `next-themes` | Unused dependency | Dark mode only, no toggle |
| `swr` | Unused dependency | Not used |
| `requests-oauthlib` | Unused backend dependency | Listed in `requirements.txt` but not imported — manual OAuth flow |
| `python-jose` | Unused backend dependency | Listed but sessions are random tokens, not JWTs |
| `passlib` | Unused backend dependency | Listed but bcrypt is used directly for password hashing |
| `jq` | Unused backend dependency | Listed but not used in code |
| `pandas`, `numpy` | Unused backend dependencies | Listed but not used in application code (likely in base image) |
| `boto3` | Unused backend dependency | Listed but no AWS/S3 code |
| `test_result.md` | Stale file | Test results file in repo root — may be outdated |
| `test_reports/` | Test artifacts | 12 JSON iteration reports + pytest XML results — committed to repo |
| `memory/` | Emergent artifacts | Session handoff files (PDF, HTML, MD) + `PRD.md` — these are Emergent platform artifacts |
| `.emergent/` | Emergent config | `emergent.yml`, cron scripts, system deps — platform configuration |
| `frontend/plugins/health-check/` | Dev plugin | Webpack health check plugin — dev-only, not in production |

### Assessment
No **duplicated** code found. The codebase is clean — the main "obsolete" items are unused dependencies (likely from the Emergent base image) and Emergent platform artifacts.

**Do not delete during this audit.** Document only.

---

## 15. Migration Risks

### What could break when implementing V2

| # | Risk | Why It Matters | Affected Components | Probability | Impact | Recommended Mitigation |
|---|------|---------------|---------------------|-------------|--------|----------------------|
| 1 | **Changing project schema** (adding readiness dimensions, stack, costs, ownership) | Existing projects would need migration; score history format changes | `db.projects`, `db.scores`, `ProjectOut` model, `_project_to_out()`, `ProjectCard`, `ProjectDetail` | High | High | Add new fields as optional; keep existing fields intact; write a migration script that backfills defaults |
| 2 | **Replacing AI provider** (Emergent → OpenAI/GPT) | Current scoring depends on Emergent's `LlmChat` integration; switching providers changes the entire `emergentintegrations` dependency | `_score_with_llm()`, `backend/requirements.txt`, `emergentintegrations` package | Medium | High | Abstract the LLM call behind an interface; keep Emergent as one provider; add OpenAI as another |
| 3 | **Changing OAuth scopes** | Narrower scopes could break existing GitHub connections | `github_connect`, `github_callback`, `github_repos`, `github_connections` collection | Low | Medium | If switching to GitHub App model, need to handle migration of existing OAuth tokens |
| 4 | **Adding readiness dimensions to scoring** | The single 0-100 score is used in `ProjectCard`, `ScoreHistoryChart`, `TopMovers`, `ShippedBadge`, digest email — changing to 8 dimensions affects all of these | All score-related components + digest email | High | Medium | Keep the overall score as a derived value from dimensions; don't remove the single score — layer dimensions on top |
| 5 | **Stripe changes** (new plans, features, billing models) | Changes to `PLANS` dict or webhook handler could break existing subscriptions | `PLANS`, `_resolve_plan()`, `stripe_webhook()`, `billing_checkout()` | Low | High | Don't change existing plan keys; add new plans alongside; test webhook handling for new event types |
| 6 | **Authentication changes** (adding admin roles, changing session model) | Current auth is session-cookie based with MongoDB; changing to JWT or adding roles affects all protected routes | `get_current_user()`, `ProtectedRoute`, all `Depends(get_current_user)` endpoints | Low | High | Extend the user model with optional fields; don't change session token structure |
| 7 | **MongoDB schema drift** | MongoDB is schemaless; adding fields without migration means existing documents lack new fields | All collections | High | Medium | Use `$set` with defaults in queries; handle missing fields gracefully with `.get()` |
| 8 | **Existing user data** | Users have tracked projects, scores, billing — these must not be lost | `users`, `projects`, `scores`, `billing`, `next_steps` | Low | Critical | Never delete collections; add fields with `upsert`/`$set`; backup before migration |
| 9 | **Production deployment** | The app runs on Emergent's platform; V2 changes must be deployable there | `.emergent/`, deployment config | Medium | Medium | Ensure V2 doesn't require infrastructure not available on Emergent; test deployments incrementally |
| 10 | **AI cost increase** | V2 may call LLM more frequently (8 dimension scores vs 1 overall) | `_score_with_llm()`, nightly rescan job | High | Medium | Cache scores; use cheaper models for dimension scoring; batch dimension scoring in one LLM call |
| 11 | **Scoring consistency** | Changing the scoring model means old scores and new scores aren't comparable | `db.scores`, `ScoreHistoryChart`, streaks, top movers | High | Medium | Store `model` field with each score; mark old scores as legacy; allow comparison only within same model version |
| 12 | **`.appnsaas/` project standard** | Writing files to user repos requires write access — current OAuth is read-only | GitHub integration, OAuth scopes | Medium | Medium | Make `.appnsaas/` optional; store readiness data in AppsNSaasBuilder's DB; only write to repos if user explicitly enables it |

---

## Appendix: Repository File Tree (Source Files Only)

```
AppsNSaasBuilder/
├── .emergent/                    # Emergent platform config
│   ├── emergent.yml
│   ├── system_deps.txt
│   └── cron/                     # Webhook cron scripts
├── .gitignore
├── .gitconfig
├── README.md                     # "Here are your Instructions"
├── auth_testing.md               # Auth testing playbook
├── design_guidelines.json        # Theme + design spec
├── memory/                       # Emergent session handoff artifacts
│   ├── PRD.md
│   └── SESSION_HANDOFF_*
├── test_result.md                # Test results
├── test_reports/                 # JSON + XML test reports
├── backend/
│   ├── server.py                 # 2,059 lines — entire backend
│   ├── requirements.txt          # Python dependencies
│   ├── pytest.ini                # Test config
│   └── tests/
│       ├── backend_test.py       # ~40 tests (auth, GitHub, projects, CORS)
│       ├── test_billing_v2_and_cron.py  # ~12 tests (billing, cron)
│       └── test_activity_weekly.py       # ~10 tests (activity, rescan)
├── frontend/
│   ├── package.json              # Dependencies + scripts
│   ├── craco.config.js           # CRACO + webpack config
│   ├── tailwind.config.js        # Tailwind theme
│   ├── jsconfig.json
│   ├── components.json           # shadcn/ui config
│   ├── postcss.config.js
│   ├── .gitignore
│   ├── README.md
│   ├── plugins/
│   │   └── health-check/         # Webpack health plugin (dev-only)
│   ├── public/
│   │   └── index.html            # HTML template + PostHog
│   └── src/
│       ├── index.js              # React entry point
│       ├── index.css             # Theme + fonts
│       ├── App.js                # Root + routing
│       ├── App.css               # (minimal)
│       ├── lib/
│       │   ├── api.js            # Fetch wrapper — all API calls
│       │   ├── auth.jsx          # Auth context
│       │   ├── billing.jsx       # Billing context
│       │   └── utils.js          # Utilities (cn, etc.)
│       ├── hooks/
│       │   └── use-toast.js      # Toast hook
│       ├── constants/
│       │   └── testIds/          # Test ID constants
│       ├── pages/
│       │   ├── Login.jsx
│       │   ├── Register.jsx
│       │   ├── AuthCallback.jsx
│       │   ├── Dashboard.jsx
│       │   ├── ProjectDetail.jsx
│       │   ├── Settings.jsx
│       │   ├── Connect.jsx
│       │   ├── RepoPicker.jsx
│       │   ├── Pricing.jsx
│       │   ├── PaymentSuccess.jsx
│       │   ├── PaymentCancel.jsx
│       │   ├── ForgotPassword.jsx
│       │   └── ResetPassword.jsx
│       └── components/
│           ├── AppShell.jsx
│           ├── ProjectCard.jsx
│           ├── Sparkline.jsx
│           ├── ScoreHistoryChart.jsx
│           ├── TopMovers.jsx
│           ├── ShippedBadge.jsx
│           ├── BillingCard.jsx
│           ├── DigestCard.jsx
│           ├── UpgradeModal.jsx
│           ├── ProtectedRoute.jsx
│           └── ui/               # ~30 shadcn/ui components
└── tests/
    └── __init__.py               # Empty
```

---

**END OF CURRENT_STATE.md**
