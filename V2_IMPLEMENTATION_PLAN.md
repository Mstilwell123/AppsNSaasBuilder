# V2_IMPLEMENTATION_PLAN.md
## AppsNSaasBuilder — V2 Implementation Plan

**Source:** `CURRENT_STATE.md` + `V2_GAP_ANALYSIS.md`  
**Date:** August 18, 2026  
**Status:** PROPOSED — awaiting owner approval  

---

## How This Plan Was Derived

Sprint order is determined by:
1. **Dependencies** — systems that other systems need must come first
2. **Security** — security issues are addressed before features that would compound them
3. **Migration risk** — schema changes that affect existing data are done carefully and early
4. **Product value** — highest-value features are prioritized after foundation is solid

---

## Sprint 0 — Safety & Foundation

### Purpose
Address security issues, add the AI provider abstraction layer, and lay the groundwork for multi-dimensional data — all without breaking any existing functionality.

### Features
1. **Make `TOKEN_ENCRYPTION_KEY` required** — fail at startup if missing
2. **Add API rate limiting** on scan endpoints (prevent scan spam)
3. **Abstract LLM provider** — create an interface that both Emergent/Claude and OpenAI/GPT can implement behind
4. **Add OpenAI/GPT as an alternative scoring provider** (configurable via env)
5. **Add `model` + `model_version` fields to score storage** (already partially present: `model` exists, add version tracking)
6. **Add cross-user isolation test** — explicitly test that user A cannot access user B's projects/scores/steps
7. **Add Stripe webhook mock tests** — test webhook handler with mock events
8. **Clean up unused dependencies** (optional, non-blocking)

### Existing Systems to Reuse
- `server.py` — add LLM abstraction without changing existing scoring
- `backend_test.py` — extend with new tests
- `requirements.txt` — add `openai` package

### Dependencies
- None (this is the foundation sprint)

### Expected Files/Systems Affected
- `backend/server.py` — LLM abstraction, rate limiting, startup validation
- `backend/requirements.txt` — add `openai`, `slowapi` (rate limiter)
- `backend/tests/` — new test files
- `frontend/` — no changes

### Data Migration
- None — existing scores keep their `model` field; new scores include `model_version`

### Security Review
- **Required** — rate limiting, encryption key enforcement, LLM provider isolation

### QA Plan
- Run existing test suite (must pass without changes)
- New tests: cross-user isolation, webhook mock events, LLM provider switching
- Manual: verify existing scoring still works with default provider

### Acceptance Criteria
- App fails to start if `TOKEN_ENCRYPTION_KEY` is missing
- Scan endpoint returns 429 after N requests per minute
- LLM provider can be switched via env var without code changes
- OpenAI/GPT provider produces valid JSON scores
- Cross-user isolation test proves user A gets 404 on user B's project
- Stripe webhook mock tests pass

### Definition of Done
- All existing tests pass
- New tests pass
- Existing scoring behavior unchanged when using default (Emergent) provider
- Security issues from `CURRENT_STATE.md` section 11 are addressed

---

## Sprint 1 — Readiness Engine

### Purpose
Replace the single 0-100 score with 8 weighted readiness dimensions while preserving the existing score as one input.

### Features
1. **Extend project model** — add `readiness` sub-document with 8 dimension scores
2. **Create readiness dimension schema:**
   - Product Definition (10%)
   - Architecture (10%)
   - Core Build (25%)
   - Security (15%)
   - QA (15%)
   - Deployment (10%)
   - Business (10%)
   - Launch (5%)
3. **Extend scoring prompt** — ask LLM for dimension scores in addition to overall score
4. **Calculate overall readiness** — weighted sum of dimensions
5. **Preserve existing score** — keep as a signal; show alongside new readiness
6. **Update `ProjectOut` model** — include `readiness` object
7. **Update `ProjectCard`** — show readiness dimensions (expandable or summary)
8. **Update `ProjectDetail`** — show dimension breakdown with bar chart
9. **Update dashboard** — portfolio average now reflects readiness, not just raw score

### Existing Systems to Reuse
- `_score_with_llm()` — extend the prompt, don't replace the function
- `_gather_repo_signals()` — existing signals feed into dimensions
- `_project_to_out()` — extend with readiness data
- `ProjectCard.jsx` — extend, don't replace
- `ProjectDetail.jsx` — add dimension section
- `ScoreHistoryChart.jsx` — reuse for dimension score history
- `db.scores` — extend with `dimensions` field

### Dependencies
- Sprint 0 (AI provider abstraction)

### Expected Files/Systems Affected
- `backend/server.py` — scoring logic, project model, score storage
- `frontend/src/components/ProjectCard.jsx` — dimension display
- `frontend/src/pages/ProjectDetail.jsx` — dimension breakdown
- `frontend/src/pages/Dashboard.jsx` — portfolio readiness average
- `frontend/src/components/ScoreHistoryChart.jsx` — may need dimension toggle

### Data Migration
- Add `readiness` field to `projects` as `null` for existing projects (lazy migration — populated on next scan)
- Add `dimensions` field to `scores` for new scores (existing scores keep `dimensions: null`)
- **No destructive migration** — existing scores remain valid

### Security Review
- Not required (no new auth, GitHub, or billing changes)

### QA Plan
- Verify existing projects still display correctly
- Verify new scan produces dimension scores
- Verify overall readiness = weighted sum of dimensions
- Verify score history chart works with dimension data
- Test: existing project with old score format → scan → new score with dimensions

### Acceptance Criteria
- New scans produce 8 dimension scores + overall readiness
- Existing projects display without errors (old scores show as "legacy")
- Overall readiness score is a weighted sum of dimensions
- `ProjectDetail` shows dimension breakdown
- `ProjectCard` shows readiness summary
- Score history preserves old scores and shows new ones

### Definition of Done
- All existing tests pass
- Readiness dimensions are stored and displayed
- Existing scoring flow continues to work
- No existing data is lost or corrupted

---

## Sprint 2 — Next Best Action

### Purpose
Extend the next-steps feature into context-aware "Next Best Action" recommendations that consider blockers, security, stage, readiness, business impact, and recommended Hermes skills.

### Features
1. **Enhance next-step generation** — include context: current readiness dimensions, project stage, blockers
2. **Add "recommended Hermes skill" field** to next steps (e.g., "Authentication Audit", "Security Audit")
3. **Add "readiness impact" field** to next steps (e.g., "+6 Security")
4. **Update `NextStepOut` model** — add `recommended_skill` and `readiness_impact`
5. **Update `ProjectDetail`** — show recommended skill and impact alongside each step
6. **Preserve existing next-step behavior** — steps still toggle, still have weights

### Existing Systems to Reuse
- `_score_with_llm()` — extend prompt to include skill recommendations
- `next_steps` collection — extend, don't replace
- `ProjectDetail.jsx` next-steps checklist — extend with new fields
- Next-step preservation on rescan — keep working

### Dependencies
- Sprint 1 (Readiness Engine — dimensions provide context for recommendations)

### Expected Files/Systems Affected
- `backend/server.py` — scoring prompt, next-step model
- `frontend/src/pages/ProjectDetail.jsx` — next-step display
- `db.next_steps` — add `recommended_skill`, `readiness_impact` fields

### Data Migration
- Existing next steps get `recommended_skill: null` and `readiness_impact: null` — populated on next scan

### Security Review
- Not required

### QA Plan
- Verify existing next steps still display and toggle
- Verify new scans produce skill recommendations
- Verify readiness impact is a positive integer

### Acceptance Criteria
- New next steps include recommended skill and readiness impact
- Existing next steps display without errors
- `ProjectDetail` shows skill + impact per step

### Definition of Done
- All tests pass
- Next Best Action generates context-aware recommendations
- Existing step toggling and preservation still works

---

## Sprint 3 — My Stack

### Purpose
Allow users to catalog all software and infrastructure supporting their applications.

### Features
1. **New `stack_services` collection** — `{id, user_id, project_id?, name, category, provider, plan, owner, account_url, cost, billing_interval, renewal_date, active, notes, created_at, updated_at}`
2. **Categories:** AI, code/source control, frontend, backend, database, hosting, auth, payments, email, analytics, monitoring, domains, storage
3. **API endpoints:** CRUD for stack services
4. **Stack management UI** — list, add, edit, remove services per project
5. **Stack visualization** — grouped by category
6. **Connect stack to projects** — a service can be linked to one or more projects

### Existing Systems to Reuse
- `api.js` — add stack endpoints
- `AppShell.jsx` — add "My Stack" nav item
- shadcn/ui components — table, dialog, select, input, badges
- `ProtectedRoute` — protect stack routes

### Dependencies
- Sprint 0 (user isolation patterns)

### Expected Files/Systems Affected
- `backend/server.py` — new stack endpoints
- `frontend/src/pages/` — new Stack page
- `frontend/src/components/` — new stack components
- `frontend/src/App.js` — new routes

### Data Migration
- None — new collection

### Security Review
- **Required** — ensure user_id isolation on all stack endpoints

### QA Plan
- Cross-user isolation test: user A cannot see user B's stack services
- CRUD test: create, read, update, delete
- Verify cost and billing interval are stored correctly

### Acceptance Criteria
- Users can add, edit, and remove stack services
- Services are isolated per user
- Services can be linked to projects
- Stack is grouped by category in the UI

### Definition of Done
- All tests pass
- Stack CRUD works end-to-end
- User isolation is enforced and tested

---

## Sprint 4 — Software Cost Center

### Purpose
Help users understand how much their software portfolio costs to run.

### Features
1. **New `costs` collection** — `{id, user_id, project_id?, service_id?, amount, currency, type (fixed/variable/transactional/annual/one_time), period (monthly/annual/one_time), start_date, end_date?, notes, created_at}`
2. **Cost aggregation:** portfolio total, per-app cost, shared cost allocation
3. **Annualized cost calculation**
4. **Cost dashboard** — summary cards + breakdown table
5. **Cost per project** — total cost of all services linked to a project
6. **Shared costs** — costs split across multiple projects (allocation percentage)

### Existing Systems to Reuse
- `stack_services` from Sprint 3 — costs are linked to services
- `api.js` — add cost endpoints
- shadcn/ui table and card components

### Dependencies
- Sprint 3 (My Stack — costs are attached to services)

### Expected Files/Systems Affected
- `backend/server.py` — cost endpoints + aggregation logic
- `frontend/src/pages/` — new Cost Center page
- `frontend/src/App.js` — new route

### Data Migration
- None — new collection

### Security Review
- Required — user_id isolation

### QA Plan
- Test cost aggregation correctness
- Test shared cost allocation math
- Cross-user isolation test

### Acceptance Criteria
- Users can add cost entries (fixed, variable, one-time)
- Portfolio total cost is displayed
- Per-project cost is calculated
- Shared costs are allocated correctly
- Annualized cost is shown

### Definition of Done
- All tests pass
- Cost aggregation is accurate
- User isolation is enforced

---

## Sprint 5 — Ownership Center

### Purpose
Help users understand whether they control their important assets.

### Features
1. **Ownership tracking model** — for each project, track ownership of: repository, source, domain, database, hosting, Stripe, APIs, backups, secrets, documentation
2. **Ownership score** — calculated based on how many critical assets the user controls
3. **Ownership UI** — checklist + score per project
4. **Integration with Stack** — ownership of stack services feeds the score
5. **"NOT VERIFIED" states** — if we can't verify ownership, show that honestly

### Existing Systems to Reuse
- `stack_services` from Sprint 3 — stack services have `owner` field
- `ProjectDetail.jsx` — add Ownership tab/section
- shadcn/ui checklist components

### Dependencies
- Sprint 3 (My Stack)

### Expected Files/Systems Affected
- `backend/server.py` — ownership endpoints + scoring
- `frontend/src/pages/ProjectDetail.jsx` — ownership section
- `frontend/src/pages/` — new Ownership Center page (optional)

### Data Migration
- None — new collection or sub-document

### Security Review
- Not required (read-only feature)

### QA Plan
- Test ownership score calculation
- Test "NOT VERIFIED" display
- Test integration with stack services

### Acceptance Criteria
- Users can mark ownership status for each asset category
- Ownership score is calculated and displayed
- Unverified items show "NOT VERIFIED"
- Ownership feeds into readiness score (Security dimension)

### Definition of Done
- All tests pass
- Ownership score is honest (no fake ownership claims)
- Integration with readiness engine

---

## Sprint 6 — PRD & Documents

### Purpose
Allow users to store and manage product documents per project.

### Features
1. **PRD storage** — `db.project_documents` collection: `{id, user_id, project_id, type (prd/architecture/security/qa/deployment/changelog/readme), content, version, created_at, updated_at}`
2. **Document viewer** — markdown rendering in ProjectDetail
3. **Document editor** — simple textarea editor (no rich text for v2.1)
4. **Decision log** — `{id, user_id, project_id, title, decision, rationale, date}`
5. **Recommended documents** — show checklist of which docs a project should have

### Existing Systems to Reuse
- `ProjectDetail.jsx` — add Documents tab
- shadcn/ui tabs component
- `api.js` — add document endpoints

### Dependencies
- Sprint 1 (Project Model extension from Readiness Engine)

### Expected Files/Systems Affected
- `backend/server.py` — document endpoints
- `frontend/src/pages/ProjectDetail.jsx` — documents tab
- `frontend/src/App.js` — no new top-level routes (documents are within ProjectDetail)

### Data Migration
- None — new collection

### Security Review
- Required — user_id isolation on document endpoints

### QA Plan
- CRUD test for documents
- Cross-user isolation test
- Markdown rendering test

### Acceptance Criteria
- Users can create, view, and edit documents per project
- Documents are categorized by type
- Decision log records decisions with rationale
- Document checklist shows what's missing

### Definition of Done
- All tests pass
- Documents are isolated per user
- Markdown renders correctly

---

## Sprint 7 — `.appnsaas` Project Standard

### Purpose
Create a portable project-metadata standard that lives in the user's repository.

### Features
1. **`.appnsaas/` directory spec:** `project.json`, `readiness.json`, `stack.json`, `costs.json`, `ownership.json`, `qa.json`, `security.json`, `launch.json`, `skills.json`
2. **Generator** — export project data from AppsNSaasBuilder as `.appnsaas/` files
3. **Reader** — import `.appnsaas/` from a repo to populate project data
4. **Optional write-back** — if user enables GitHub write scope, write `.appnsaas/` to their repo
5. **The user's application should NOT depend on `.appnsaas/` to run**

### Existing Systems to Reuse
- GitHub integration — read `.appnsaas/` if present (requires GitHub contents API)
- Project model — export to JSON
- Readiness data — export to JSON
- Stack data — export to JSON

### Dependencies
- Sprint 1 (Readiness Engine)
- Sprint 3 (My Stack)
- Sprint 5 (Ownership Center)
- Sprint 0 (Security hardening — if write-back is enabled, need OAuth scope review)

### Expected Files/Systems Affected
- `backend/server.py` — export/import endpoints, `.appnsaas/` reader
- `frontend/src/pages/ProjectDetail.jsx` — export button

### Data Migration
- None — export is read-only from existing data

### Security Review
- **Required** — if write-back is enabled, OAuth scope must be reviewed and user must explicitly consent

### QA Plan
- Test export generates valid JSON files
- Test import populates project data correctly
- Test write-back requires explicit user consent
- Test `.appnsaas/` is optional (app works without it)

### Acceptance Criteria
- Export produces all `.appnsaas/` JSON files
- Import reads `.appnsaas/` and populates project data
- Write-back is opt-in only
- User's application does not depend on `.appnsaas/`

### Definition of Done
- All tests pass
- Export/import round-trips correctly
- No OAuth scope changes without user consent

---

## Sprint 8 — QA & Security Evidence

### Purpose
Distinguish "DETECTED" from "VERIFIED" for QA and security claims.

### Features
1. **Evidence model** — `{id, user_id, project_id, category (qa/security), claim, status (detected/verified/not_verified), evidence, source, verified_at}`
2. **Detection logic** — scan repo for test files, CI config, security configs (detected)
3. **Verification logic** — check if tests pass, if CI is green, if security checks pass (verified)
4. **Evidence UI** — show detected vs verified per project
5. **Feed into readiness** — QA and Security dimensions use evidence status

### Existing Systems to Reuse
- GitHub integration — read repo contents for test files, CI configs
- Readiness Engine — evidence feeds QA and Security dimensions
- `ProjectDetail.jsx` — add Evidence tab

### Dependencies
- Sprint 1 (Readiness Engine)
- Sprint 0 (AI Provider Abstraction — may use LLM for evidence analysis)

### Expected Files/Systems Affected
- `backend/server.py` — evidence collection + storage
- `frontend/src/pages/ProjectDetail.jsx` — evidence display
- New `db.evidence` collection

### Data Migration
- None — new collection

### Security Review
- Required — evidence collection must be read-only (no write to repos)

### QA Plan
- Test detection logic (finds test files, CI configs)
- Test verification logic (checks CI status if available)
- Test "DETECTED" vs "VERIFIED" display
- Test evidence feeds into readiness score

### Acceptance Criteria
- Detected items are shown with "DETECTED" badge
- Verified items are shown with "VERIFIED" badge
- Unverifiable items show "NOT VERIFIED"
- Evidence influences QA and Security readiness dimensions
- No fake or hardcoded evidence

### Definition of Done
- All tests pass
- Evidence is honest (detected ≠ verified)
- Readiness scores reflect evidence

---

## Sprint 9 — Launch Center

### Purpose
Help users track launch readiness with a checklist.

### Features
1. **Launch checklist model** — per-project checklist with items: domain configured, SSL, production env, DB connected, env vars set, tests pass, monitoring, error tracking, backup, etc.
2. **Launch readiness score** — percentage of checklist complete
3. **Launch gate** — if readiness below threshold, show warning
4. **Launch checklist UI** — in ProjectDetail

### Existing Systems to Reuse
- Readiness Engine — launch dimension feeds into overall readiness
- `ProjectDetail.jsx` — add Launch tab
- shadcn/ui checklist components

### Dependencies
- Sprint 1 (Readiness Engine)
- Sprint 8 (Evidence — some launch items are evidence-based)

### Expected Files/Systems Affected
- `backend/server.py` — launch checklist endpoints
- `frontend/src/pages/ProjectDetail.jsx` — launch tab
- New `db.launch_checklist` collection or sub-document

### Data Migration
- None — new collection

### Security Review
- Not required

### QA Plan
- Test checklist CRUD
- Test launch readiness calculation
- Test launch gate warning

### Acceptance Criteria
- Users can view and check off launch items
- Launch readiness score is calculated
- Warning shown if below threshold
- Launch score feeds into overall readiness

### Definition of Done
- All tests pass
- Launch checklist is functional
- No hardcoded "launched" states

---

## Sprint 10 — Hermes Skills Center

### Purpose
Recommend AppsNSaas-specific Hermes skills and optionally integrate with Hermes.

### Features
1. **Skills catalog** — curated list of AppsNSaas skills by category (Discovery, Product, Architecture, Build, Quality, Launch, Business)
2. **Skill recommendations** — based on readiness dimensions and next best action, recommend a specific skill
3. **Skills UI** — browsable skill catalog with descriptions
4. **Run With Hermes** — if feasible, generate Hermes task prompts from recommended skills
5. **Skill evidence** — if Hermes produces output, store as evidence

### Existing Systems to Reuse
- Next Best Action (Sprint 2) — skill recommendations link to next steps
- `ProjectDetail.jsx` — add Skills tab
- `api.js` — add skills endpoints

### Dependencies
- Sprint 2 (Next Best Action — skill recommendations)
- Sprint 1 (Readiness Engine — dimensions inform recommendations)

### Expected Files/Systems Affected
- `backend/server.py` — skills catalog + recommendation logic
- `frontend/src/pages/` — new Skills page
- `frontend/src/App.js` — new route

### Data Migration
- None — skills catalog is static configuration

### Security Review
- Required if "Run With Hermes" generates external API calls

### QA Plan
- Test skill recommendations match readiness gaps
- Test catalog is browseable
- Test Hermes integration (if implemented)

### Acceptance Criteria
- Skill catalog is browseable by category
- Skill recommendations appear in Next Best Action
- Users can see which skill addresses which readiness gap
- "Run With Hermes" generates a valid prompt (if implemented)

### Definition of Done
- All tests pass
- Skills are recommended based on actual readiness gaps
- No fake skill claims

---

## Sprint 11 — Business Center & Portfolio Economics

### Purpose
Help users understand the economics of their software portfolio.

### Features
1. **MRR calculation** — from Stripe subscription data
2. **Customer list** — from Stripe customer data
3. **ARPU** — average revenue per user
4. **Churn tracking** — from subscription status changes
5. **SaaS cost tracking** — from Cost Center data (Sprint 4)
6. **Gross software margin** — MRR minus software costs
7. **Portfolio economics dashboard** — aggregate view across all projects
8. **OpenAI/AI cost tracking** — track AI API costs

### Existing Systems to Reuse
- Stripe integration — query subscription/customer data from Stripe
- Cost Center (Sprint 4) — software costs
- `BillingCard.jsx` — extend or add new Business card
- shadcn/ui table, card, chart components

### Dependencies
- Sprint 4 (Cost Center — for margin calculation)
- Existing Stripe integration (for MRR/customers)

### Expected Files/Systems Affected
- `backend/server.py` — business metrics endpoints + Stripe queries
- `frontend/src/pages/` — new Business Center page
- `frontend/src/App.js` — new route

### Data Migration
- None — reads from existing Stripe data

### Security Review
- Required — Stripe customer data is sensitive; ensure user isolation

### QA Plan
- Test MRR calculation
- Test ARPU calculation
- Test margin calculation
- Cross-user isolation test

### Acceptance Criteria
- MRR is calculated from live Stripe data
- Customer list is displayed
- ARPU and churn are calculated
- Gross software margin = MRR - software costs
- Portfolio economics dashboard shows aggregate metrics
- All metrics show "NOT CONNECTED" if Stripe is not configured

### Definition of Done
- All tests pass
- Business metrics are real (from Stripe), not fabricated
- "NOT CONNECTED" states are shown honestly
- User isolation is enforced

---

## Sprint 12 — Idea Pipeline & Portfolio Dashboard Upgrade

### Purpose
Add the idea-to-project pipeline and upgrade the dashboard to a full portfolio command center.

### Features
1. **Idea collection** — `db.ideas` collection: `{id, user_id, title, description, status (idea/validating/validated/archived), created_at}`
2. **Idea pipeline UI** — capture, validate, promote to project
3. **Portfolio dashboard upgrade** — lifecycle stage labels, readiness breakdown, cost summary, business summary
4. **Stage tracking** — IDEA → VALIDATE → PRD → ARCHITECT → BUILD → TEST → SECURE → LAUNCH → OPERATE → GROW
5. **Dashboard widgets** — readiness average, cost summary, MRR, ownership average, shipping streak

### Existing Systems to Reuse
- `Dashboard.jsx` — extend
- `ProjectCard.jsx` — add stage badge
- Readiness Engine (Sprint 1) — readiness data
- Cost Center (Sprint 4) — cost data
- Business Center (Sprint 11) — MRR data

### Dependencies
- Sprints 1-11 (all preceding features provide data for the dashboard)

### Expected Files/Systems Affected
- `backend/server.py` — ideas endpoints, stage tracking
- `frontend/src/pages/Dashboard.jsx` — full upgrade
- `frontend/src/pages/` — new Idea Pipeline page
- `frontend/src/App.js` — new route

### Data Migration
- Add `stage` field to existing projects (default: "BUILD" or inferred from readiness)

### Security Review
- Required — user_id isolation on ideas collection

### QA Plan
- Test idea CRUD
- Test promote-to-project flow
- Test dashboard widget data accuracy
- Cross-user isolation test

### Acceptance Criteria
- Users can capture ideas
- Ideas can be promoted to tracked projects
- Projects show lifecycle stage
- Dashboard shows readiness, cost, business, and ownership summaries
- All data is real — no fabricated metrics

### Definition of Done
- All tests pass
- Idea pipeline works end-to-end
- Dashboard is a comprehensive portfolio command center
- No fake or hardcoded data

---

## Sprint 13 — PWA & Polish

### Purpose
Make AppsNSaasBuilder installable, offline-capable, and mobile-optimized.

### Features
1. **`manifest.json`** — app name, icons, theme color, display mode
2. **App icons** — 192px and 512px
3. **Service worker** — basic caching for offline shell
4. **Safe-area support** — `env(safe-area-inset-*)` + `viewport-fit=cover`
5. **Mobile navigation** — dedicated mobile nav if needed
6. **Install prompt** — PWA install banner

### Existing Systems to Reuse
- `frontend/public/index.html` — add manifest link
- `tailwind.config.js` — responsive utilities already present
- `index.css` — add safe-area CSS

### Dependencies
- All preceding sprints (PWA wraps the complete app)

### Expected Files/Systems Affected
- `frontend/public/` — manifest.json, icons
- `frontend/public/index.html` — manifest link, viewport update
- `frontend/src/index.css` — safe-area CSS
- `frontend/src/serviceWorker.js` — new service worker registration

### Data Migration
- None

### Security Review
- Not required (PWA is frontend-only)

### QA Plan
- Test installability (Lighthouse PWA audit)
- Test offline shell loads
- Test mobile layout
- Test safe-area handling

### Acceptance Criteria
- App is installable on mobile/desktop
- Offline shell loads (cached HTML/CSS/JS)
- Safe areas are respected on notched devices
- Mobile navigation works

### Definition of Done
- Lighthouse PWA audit passes
- App installs and runs offline (shell only — data requires network)
- No layout regressions on mobile

---

## Sprint Summary

| Sprint | Name | Key Outcome | Dependencies |
|--------|------|-------------|--------------|
| 0 | Safety & Foundation | Secure base + AI abstraction | None |
| 1 | Readiness Engine | 8-dimensional scoring | Sprint 0 |
| 2 | Next Best Action | Context-aware recommendations + skill links | Sprint 1 |
| 3 | My Stack | Infrastructure catalog | Sprint 0 |
| 4 | Software Cost Center | Cost tracking + aggregation | Sprint 3 |
| 5 | Ownership Center | Asset ownership + score | Sprint 3 |
| 6 | PRD & Documents | Document management | Sprint 1 |
| 7 | `.appnsaas` Standard | Portable project metadata | Sprints 1, 3, 5 |
| 8 | QA & Security Evidence | Detected vs Verified | Sprints 0, 1 |
| 9 | Launch Center | Launch checklist + gate | Sprints 1, 8 |
| 10 | Hermes Skills Center | Skill catalog + recommendations | Sprints 1, 2 |
| 11 | Business Center & Economics | MRR, ARPU, margins | Sprint 4 |
| 12 | Idea Pipeline & Dashboard | Full lifecycle + command center | Sprints 1-11 |
| 13 | PWA & Polish | Installable + offline | All preceding |

---

**END OF V2_IMPLEMENTATION_PLAN.md**
