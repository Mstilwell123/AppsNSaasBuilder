# V2_GAP_ANALYSIS.md
## AppsNSaasBuilder — V2 Gap Analysis

**Source of truth:** `CURRENT_STATE.md` (existing-conditions audit)  
**Target state:** V2 Master PRD (software-business command center for AI-powered founders)  
**Date:** August 18, 2026  

---

## Classification Legend

| Status | Meaning | Default Action |
|--------|---------|----------------|
| **EXISTS** | Substantially implemented and usable | Preserve unless improvement is explicitly required |
| **PARTIAL** | Meaningful foundation exists; additional implementation required | Extend the existing implementation |
| **MISSING** | No meaningful implementation exists | New implementation required |
| **NEEDS_REFACTOR** | Exists but current design is unsuitable for V2 | Refactor deliberately while preserving working behavior |
| **NEEDS_SECURITY_REVIEW** | Exists but security must be resolved before expansion/release | Security review before further implementation |

---

## V2 Gap Analysis Table

### Portfolio & Dashboard

| V2 Requirement | Status | Existing System | Gap | Recommended Action | Dependencies | Risk |
|----------------|--------|-----------------|-----|-------------------|--------------|------|
| Portfolio Dashboard | EXISTS | `Dashboard.jsx` — project grid, portfolio avg, top movers, shipped badge | V2 readiness indicators missing; no multi-dimensional view | Extend dashboard with readiness dimension display | Readiness Engine | Medium |
| My Apps | EXISTS | `Dashboard.jsx` + `ProjectCard.jsx` — project grid with scores, sparklines | V2 wants lifecycle stage labels (IDEA→VALIDATE→…→SHIP); current has no stage concept | Add stage field to project model; show as badge/label | Project Model | Low |
| Idea Pipeline | MISSING | No idea capture or pipeline exists | Entire idea-to-project pipeline required | New `ideas` collection + idea capture UI + promote-to-project flow | Project Model | Low |
| Build Readiness | PARTIAL | Single 0-100 LLM score + weighted completion % | V2 wants 8 weighted dimensions (Product 10%, Architecture 10%, Core Build 25%, Security 15%, QA 15%, Deployment 10%, Business 10%, Launch 5%); current is single-dimensional | Preserve existing score as one signal; add dimension model; expand scoring | Project Model, AI Provider | High |
| Product Score | MISSING | No "product definition" dimension | No way to score product definition quality | New dimension + scoring prompt | Readiness Engine | Medium |
| Architecture Score | MISSING | No "architecture" dimension | No way to score architecture quality | New dimension + scoring prompt | Readiness Engine | Medium |
| Core Build Score | PARTIAL | Existing 0-100 LLM score covers some build signals | Not separated as a distinct dimension; mixed into overall score | Extract as its own dimension; preserve existing signals | Readiness Engine | Medium |
| Security Score | MISSING | No security dimension; security is a V2 concept | No way to score security posture of a project | New dimension + scoring prompt + evidence collection | Readiness Engine, Security Evidence | High |
| QA Score | MISSING | No QA dimension; no test coverage analysis | No way to score QA quality | New dimension + scoring prompt + evidence collection | Readiness Engine, QA Evidence | Medium |
| Deployment Score | PARTIAL | `ci_status` (configured/no_ci) exists; `live_url` exists | Not a score; just presence checks. No deployment readiness assessment | Convert to dimension; preserve existing CI/live signals as inputs | Readiness Engine | Medium |
| Business Score | MISSING | No business metrics dimension | No way to score business readiness | New dimension + scoring prompt | Readiness Engine | Medium |
| Launch Score | MISSING | No launch readiness dimension | No way to score launch readiness | New dimension + scoring prompt | Readiness Engine | Low |
| Next Best Action | PARTIAL | LLM generates 3-6 next steps with weights per scan | V2 wants context-aware recommendations (blockers, security, stage, business impact, Hermes skill); current is generic LLM next steps | Extend next-step generation with context; add Hermes skill recommendations | Readiness Engine, Hermes Skills | Medium |

### My Stack & Infrastructure

| V2 Requirement | Status | Existing System | Gap | Recommended Action | Dependencies | Risk |
|----------------|--------|-----------------|-----|-------------------|--------------|------|
| My Stack | MISSING | No stack/infrastructure tracking | Entire stack management module required | New `stack_services` collection + stack UI + service CRUD | Project Model | Low |
| Stack Visualization | MISSING | No stack visualization | No way to visualize tech stack per project | New UI component showing stack by category | My Stack | Low |
| Stack Health | MISSING | No stack health monitoring | No way to assess stack health (deprecated, security advisories) | New health check logic per service | My Stack | Medium |

### Cost Center

| V2 Requirement | Status | Existing System | Gap | Recommended Action | Dependencies | Risk |
|----------------|--------|-----------------|-----|-------------------|--------------|------|
| Software Cost Center | MISSING | No cost tracking | Entire cost tracking module required | New `costs` collection + cost entry UI + aggregation | My Stack | Low |
| Shared Costs | MISSING | No shared cost allocation | No way to track costs shared across multiple apps | New shared-cost model + allocation logic | Software Cost Center | Low |
| Cost Allocation | MISSING | No cost allocation | No way to allocate costs to specific apps | New allocation logic + UI | Software Cost Center | Low |
| Cost Forecasting | MISSING | No cost forecasting | No way to project future costs | New forecasting logic (later sprint) | Software Cost Center | Low |

### Ownership Center

| V2 Requirement | Status | Existing System | Gap | Recommended Action | Dependencies | Risk |
|----------------|--------|-----------------|-----|-------------------|--------------|------|
| Ownership Center | MISSING | Limited metadata (repo, live_url); no ownership tracking | No way to track who owns what infrastructure | New ownership tracking + UI | My Stack | Low |
| Ownership Score | MISSING | No ownership scoring | No way to calculate how much the user actually controls | New scoring logic based on ownership flags | Ownership Center | Medium |

### PRD & Documents

| V2 Requirement | Status | Existing System | Gap | Recommended Action | Dependencies | Risk |
|----------------|--------|-----------------|-----|-------------------|--------------|------|
| PRD Center | MISSING | No PRD management | No way to store/view/manage PRDs per project | New PRD storage + viewer | Project Model | Low |
| Architecture Documents | MISSING | No architecture doc management | No way to store/view architecture docs | New doc storage + viewer | PRD Center | Low |
| Project Decisions | MISSING | No decision log | No way to record architectural/product decisions | New decision log + UI | PRD Center | Low |
| `.appnsaas` Project Standard | MISSING | No project standard files | No portable project metadata in user repos | New `.appnsaas/` spec + generator + reader | Project Model, Ownership Center | Medium |

### Hermes Skills

| V2 Requirement | Status | Existing System | Gap | Recommended Action | Dependencies | Risk |
|----------------|--------|-----------------|-----|-------------------|--------------|------|
| Hermes Skills Center | MISSING | No Hermes skill integration | No way to view/recommend Hermes skills | New skills library + recommendation engine | Readiness Engine | Medium |
| Skill Recommendations | MISSING | No skill recommendations | Next steps don't recommend Hermes skills | Extend Next Best Action with skill recommendations | Hermes Skills Center, Next Best Action | Low |
| Run With Hermes | MISSING | No Hermes integration | No way to launch Hermes tasks from the app | New Hermes integration (if feasible) | Hermes Skills Center | Medium |
| QA Evidence | MISSING | No evidence collection/verification | No way to collect and verify QA evidence | New evidence model + collection logic | Readiness Engine | Medium |
| Security Evidence | MISSING | No security evidence collection | No way to collect and verify security evidence | New evidence model + collection logic | Readiness Engine | High |
| Launch Center | MISSING | No launch readiness tracking | No way to track launch readiness checklist | New launch checklist + readiness gate | Readiness Engine | Low |

### Business & Economics

| V2 Requirement | Status | Existing System | Gap | Recommended Action | Dependencies | Risk |
|----------------|--------|-----------------|-----|-------------------|--------------|------|
| Business Center | MISSING | No business metrics tracking | No way to track MRR, customers, ARPU, churn | New business metrics module + Stripe integration | Stripe Integration | Medium |
| MRR | MISSING | Stripe billing exists but no MRR calculation | No revenue tracking | New MRR calculation from Stripe data | Stripe Integration | Medium |
| Customers | MISSING | Stripe customers exist but no customer list | No customer management view | New customer list from Stripe | Stripe Integration | Low |
| ARPU | MISSING | No ARPU calculation | No average revenue per user metric | New ARPU calculation | MRR, Customers | Low |
| SaaS Cost | MISSING | No SaaS cost tracking | No way to track software costs vs. revenue | New cost tracking + margin calculation | Software Cost Center, MRR | Low |
| Portfolio Economics | MISSING | No portfolio economics view | No way to see portfolio-wide economics | New portfolio economics dashboard | MRR, SaaS Cost, ARPU | Medium |
| OpenAI Cost Tracking | MISSING | No AI cost tracking | No way to track AI/API costs per project | New AI cost tracking module | Software Cost Center | Low |

### Cross-Cutting Concerns

| V2 Requirement | Status | Existing System | Gap | Recommended Action | Dependencies | Risk |
|----------------|--------|-----------------|-----|-------------------|--------------|------|
| GitHub Hardening | NEEDS_SECURITY_REVIEW | OAuth with `public_repo` scope (broader than needed for read-only) | Scope grants write access; should use narrower scope or GitHub App model | Security review of OAuth scope; consider GitHub App migration | Auth | Medium |
| AI Provider Abstraction | NEEDS_REFACTOR | Hardcoded to Emergent `LlmChat` + Claude Haiku 4.5 | V2 wants OpenAI/GPT as preferred model; current is tightly coupled to Emergent | Abstract LLM interface; keep Emergent as one provider; add OpenAI | Readiness Engine | High |
| Authentication | EXISTS | Hybrid Google + local password with bcrypt, session cookies, rate limiting, password reset | V2 may need admin roles; current auth is complete for current scope | Preserve; extend with optional admin role if needed | None | Low |
| Stripe Integration | EXISTS | Complete subscription billing with checkout, webhooks, portal, trial, plan enforcement | V2 may need new plan tiers; current Stripe is complete for billing | Preserve; extend plans as needed | None | Low |
| GitHub Integration | EXISTS | Read-only OAuth, metadata scanning, scoring, next steps | V2 may need `.appnsaas/` write capability (would require write scope) | Preserve read-only; add write capability only if explicitly required | Auth | Medium |
| PWA | MISSING | Theme color meta only; no manifest, no service worker, no installability | Full PWA support required for V2 | New manifest.json, icons, service worker, offline support | Frontend | Low |

---

## Implementation Dependency Map

Derived from actual repository findings — not assumptions from the PRD.

```
PROJECT DATA MODEL (existing: projects, scores, next_steps)
        ↓
READINESS DATA MODEL (new: dimensions, weights, evidence)
        ↓
READINESS ENGINE (new: multi-dimensional scoring + LLM integration)
        ↓
NEXT BEST ACTION (extend: context-aware recommendations + Hermes skill links)
        ↓
DASHBOARD UPGRADE (extend: dimension display, readiness breakdown)
```

```
STACK MODEL (new: stack_services, costs, ownership)
        ↓
MY STACK (new: stack management UI)
        ↓
STACK HEALTH (new: health checks per service)
        ↓
SOFTWARE COST CENTER (new: cost tracking + aggregation)
        ↓
OWNERSHIP CENTER (new: ownership tracking + scoring)
        ↓
SAAS ECONOMICS (new: MRR, ARPU, margins, portfolio economics)
```

```
SKILL STANDARD (new: .appnsaas/ spec)
        ↓
SKILLS LIBRARY (new: Hermes skill catalog)
        ↓
SKILL RECOMMENDATIONS (extend: Next Best Action → recommended skill)
        ↓
RUN WITH HERMES (new: Hermes integration)
        ↓
EVIDENCE VERIFICATION (new: QA + security evidence collection)
        ↓
READINESS (feeds back into Readiness Engine scores)
```

```
PRD CENTER (new: PRD storage + viewer)
        ↓
ARCHITECTURE DOCUMENTS (new: doc management)
        ↓
PROJECT DECISIONS (new: decision log)
        ↓
.appnsaas PROJECT STANDARD (new: portable project metadata)
        ↓
LAUNCH CENTER (new: launch readiness checklist)
        ↓
BUSINESS CENTER (new: MRR, customers, economics)
```

**Cross-cutting dependencies:**

```
AI PROVIDER ABSTRACTION (prerequisite: before Readiness Engine)
        ↓
READINESS ENGINE (depends on: AI Provider Abstraction + Project Model)
        ↓
ALL V2 FEATURES (depend on: Readiness Engine for dimension scores)
```

```
SECURITY HARDENING (prerequisite: before any write operations)
        ↓
GITHUB WRITE CAPABILITY (if needed for .appnsaas/)
        ↓
.appnsaas PROJECT STANDARD
```

---

## V2 Risk Register

| # | Risk | Severity | Probability | Impact | Mitigation | Owner |
|---|------|----------|-------------|--------|------------|-------|
| 1 | **AI provider migration breaks scoring** — switching from Emergent/Claude to OpenAI/GPT changes score baselines, making historical comparisons invalid | High | Medium | High | Store `model` + `model_version` with each score; don't compare across model versions; run both in parallel during transition | Backend |
| 2 | **Schema migration corrupts existing user data** — adding readiness dimensions to `projects` or `scores` could break existing documents | High | Medium | Critical | Add fields as optional with defaults; never remove existing fields; backup MongoDB before deployment | Backend |
| 3 | **Scoring inconsistency** — multi-dimensional scoring may produce wildly different totals than current single score, confusing existing users | Medium | High | Medium | Keep overall score as a weighted sum of dimensions; display "v1 score" and "v2 score" side by side during transition | Product |
| 4 | **GitHub OAuth scope widening** — if V2 needs write access for `.appnsaas/`, existing read-only tokens must be re-authorized | Medium | Medium | Medium | Don't change OAuth scope unless write is explicitly required; if needed, prompt users to re-connect with new scope | Auth |
| 5 | **Stripe plan changes break existing subscriptions** — adding/renaming plans could affect active subscribers | High | Low | High | Don't change existing plan keys; add new plans alongside existing ones; test webhook handling for all event types | Billing |
| 6 | **Authentication changes lock out existing users** — adding admin roles or changing session model could invalidate active sessions | High | Low | Critical | Extend user model with optional fields; don't change session token structure; test with existing session data | Auth |
| 7 | **AI cost explosion** — 8 dimension scores × nightly rescan × all projects could be expensive | Medium | High | Medium | Batch dimensions in one LLM call; use cheaper models for dimension scoring; cache scores; add rate limiting on scan endpoint | Backend |
| 8 | **Security regression** — new features (write to repos, Hermes integration) introduce new attack surfaces | High | Medium | High | Security review before each sprint that touches auth, GitHub, or external integrations; add CSRF protection; scope OAuth minimally | Security |
| 9 | **Emergent platform dependency** — V2 features may not be deployable on Emergent's infrastructure | Medium | Medium | Medium | Ensure V2 doesn't require infrastructure not available on Emergent; test deployments incrementally | DevOps |
| 10 | **Existing user confusion** — UI changes (multi-dimensional scores, new modules) could overwhelm existing users | Low | High | Low | Incremental rollout; preserve existing views; add "what's new" guidance | Product |
| 11 | **Test coverage regression** — V2 features added without tests; existing tests break on schema changes | Medium | Medium | Medium | Add tests for every new feature; run existing tests before merging; add E2E tests for critical flows | QA |
| 12 | **Webhook reliability** — Stripe webhook handler is not tested; new event types could be missed | Medium | Medium | High | Add webhook event tests with mock Stripe events; handle unknown event types gracefully; log all webhook events | Billing |
| 13 | **Cross-user data leakage** — new collections (stack, costs, ownership) might not have user_id isolation | High | Low | Critical | Enforce `user_id` on every new collection; add cross-user isolation tests; review every new endpoint for auth | Security |
| 14 | **Production data loss** — destructive operations during migration could delete user projects, scores, billing | Critical | Low | Critical | Never use `delete_many` without `user_id` filter; backup before every migration; test migrations on staging data first | Backend |
| 15 | **Token encryption key rotation** — if `TOKEN_ENCRYPTION_KEY` changes, all stored GitHub tokens become undecryptable | High | Low | High | Never rotate the key without a migration plan; support key rotation with dual-key decryption during transition | Security |

---

**END OF V2_GAP_ANALYSIS.md**
