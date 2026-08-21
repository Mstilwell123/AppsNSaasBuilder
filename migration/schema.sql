-- ============================================================================
-- AppsNSaasBuilder — Postgres schema (Supabase)
-- Ported from the MongoDB (Motor) data model in backend/server.py
-- Conventions:
--   * Every user-owned table carries user_id (text) for isolation.
--   * IDs are text (app generates "user_xxxx" / "proj_xxxx" / uuid hex today).
--   * JSON-ish fields (dimensions, languages, sparkline, project_ids) -> jsonb.
--   * Timestamps stored as timestamptz (Mongo stored ISO strings; PG parses both).
--   * created_at/updated_at default now() where the app doesn't always set them.
-- ============================================================================

create extension if not exists pgcrypto;  -- for gen_random_uuid() if needed

-- ---------------------------------------------------------------------------
-- users (auth profile + trial state)
-- ---------------------------------------------------------------------------
create table if not exists users (
  user_id               text primary key,
  email                 text not null unique,
  name                  text,
  picture               text,
  password_hash         text,                 -- bcrypt $2b$... (nullable = oauth-only)
  weekly_digest_enabled boolean not null default true,
  github_connected      boolean not null default false,
  trial_started_at      timestamptz,
  trial_ends_at         timestamptz,
  locked_at             timestamptz,          -- set when trial expired w/o subscription
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);
create index if not exists idx_users_email on users (lower(email));

-- ---------------------------------------------------------------------------
-- user_sessions (custom session tokens — kept in Option A, not Supabase Auth)
-- ---------------------------------------------------------------------------
create table if not exists user_sessions (
  id            bigint generated always as identity primary key,
  user_id       text not null references users(user_id) on delete cascade,
  session_token text not null unique,
  expires_at    timestamptz not null,
  created_at    timestamptz not null default now()
);
create index if not exists idx_sessions_user on user_sessions(user_id);
create index if not exists idx_sessions_token on user_sessions(session_token);

-- ---------------------------------------------------------------------------
-- password_reset_tokens (single-use, SHA-256 hashed at rest)
-- ---------------------------------------------------------------------------
create table if not exists password_reset_tokens (
  id          bigint generated always as identity primary key,
  user_id     text not null references users(user_id) on delete cascade,
  token_hash  text not null,
  expires_at  timestamptz not null,
  used_at     timestamptz,
  created_at  timestamptz not null default now()
);
create index if not exists idx_prt_user on password_reset_tokens(user_id);
create index if not exists idx_prt_hash on password_reset_tokens(token_hash);

-- ---------------------------------------------------------------------------
-- login_attempts (rate limiting on login)
-- ---------------------------------------------------------------------------
create table if not exists login_attempts (
  id          bigint generated always as identity primary key,
  email       text not null,
  success     boolean not null,
  created_at  timestamptz not null default now()
);
create index if not exists idx_login_attempts_email on login_attempts(lower(email), created_at);

-- ---------------------------------------------------------------------------
-- github_connections (encrypted OAuth tokens — one per user)
-- ---------------------------------------------------------------------------
create table if not exists github_connections (
  user_id          text primary key references users(user_id) on delete cascade,
  github_user_id   text,
  github_username  text,
  encrypted_token  text not null,             -- Fernet ciphertext
  scopes           text,
  connected_at     timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- github_oauth_states (short-lived CSRF state tokens)
-- ---------------------------------------------------------------------------
create table if not exists github_oauth_states (
  state       text primary key,
  user_id     text not null references users(user_id) on delete cascade,
  expires_at  timestamptz not null,
  created_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- projects (tracked GitHub repos)
-- ---------------------------------------------------------------------------
create table if not exists projects (
  id                text primary key,
  user_id           text not null references users(user_id) on delete cascade,
  github_repo_id    bigint not null,
  name              text not null,
  full_name         text not null,
  private           boolean not null default false,
  primary_language  text,
  languages         jsonb not null default '{}'::jsonb,     -- {lang: bytes}
  stars             integer not null default 0,
  forks             integer not null default 0,
  open_issues       integer not null default 0,
  default_branch    text not null default 'main',
  live_url          text,
  ci_status         text not null default 'unknown',        -- configured|no_ci|unknown
  commit_sparkline  jsonb not null default '[]'::jsonb,     -- [int] last 12 weeks
  last_commit_at    timestamptz,
  one_line_summary  text,
  added_at          timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  unique (user_id, github_repo_id)
);
create index if not exists idx_projects_user on projects(user_id);

-- ---------------------------------------------------------------------------
-- scores (LLM readiness score history; latest per project drives the UI)
-- ---------------------------------------------------------------------------
create table if not exists scores (
  id          text primary key,
  user_id     text not null references users(user_id) on delete cascade,
  project_id  text not null references projects(id) on delete cascade,
  score       integer not null,
  rationale   text,
  model       text,                           -- "provider:model_id"
  dimensions  jsonb not null default '{}'::jsonb,  -- 8 readiness dims {product:.., ...}
  scored_at   timestamptz not null default now()
);
create index if not exists idx_scores_project on scores(project_id, scored_at desc);
create index if not exists idx_scores_user on scores(user_id);

-- ---------------------------------------------------------------------------
-- next_steps (weighted recommendations per project)
-- ---------------------------------------------------------------------------
create table if not exists next_steps (
  id                text primary key,
  user_id           text not null references users(user_id) on delete cascade,
  project_id        text not null references projects(id) on delete cascade,
  text              text not null,
  weight            integer not null default 1,
  "order"           integer not null default 1,
  done              boolean not null default false,
  recommended_skill text,
  readiness_impact  integer,
  completed_at      timestamptz,
  created_at        timestamptz not null default now()
);
create index if not exists idx_next_steps_project on next_steps(project_id, "order");
create index if not exists idx_next_steps_user on next_steps(user_id);

-- ---------------------------------------------------------------------------
-- scans (async AI scan jobs)
-- ---------------------------------------------------------------------------
create table if not exists scans (
  id          text primary key,
  user_id     text not null references users(user_id) on delete cascade,
  project_id  text not null references projects(id) on delete cascade,
  status      text not null,                  -- running|done|error
  error       text,
  started_at  timestamptz not null default now(),
  finished_at timestamptz
);
create index if not exists idx_scans_project on scans(project_id, started_at desc);

-- ---------------------------------------------------------------------------
-- billing (Stripe customer map — one per user)
-- ---------------------------------------------------------------------------
create table if not exists billing (
  user_id      text primary key references users(user_id) on delete cascade,
  customer_id  text not null,                 -- Stripe cus_...
  email        text,
  updated_at   timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- payment_transactions (checkout sessions / subscription state)
-- ---------------------------------------------------------------------------
create table if not exists payment_transactions (
  id              bigint generated always as identity primary key,
  user_id         text not null references users(user_id) on delete cascade,
  session_id      text unique,                -- Stripe checkout session
  subscription_id text,
  customer_id     text,
  plan_key        text,
  lookup_key      text,
  amount          numeric(10,2),
  currency        text,
  status          text,                       -- Stripe session status
  payment_status  text,                       -- paid|unpaid|...
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);
create index if not exists idx_paytx_user on payment_transactions(user_id);

-- ---------------------------------------------------------------------------
-- stack_services (My Stack catalog)
-- ---------------------------------------------------------------------------
create table if not exists stack_services (
  id               text primary key,
  user_id          text not null references users(user_id) on delete cascade,
  name             text not null,
  category         text not null,
  provider         text,
  plan             text,
  owner            text,
  account_url      text,
  cost             numeric(10,2),
  billing_interval text,
  renewal_date     date,
  active           boolean not null default true,
  notes            text,
  project_ids      jsonb not null default '[]'::jsonb,   -- [project_id]
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);
create index if not exists idx_stack_user on stack_services(user_id);

-- ---------------------------------------------------------------------------
-- costs (Software Cost Center)
-- ---------------------------------------------------------------------------
create table if not exists costs (
  id          text primary key,
  user_id     text not null references users(user_id) on delete cascade,
  service_id  text references stack_services(id) on delete set null,
  project_id  text references projects(id) on delete set null,
  amount      numeric(10,2) not null,
  currency    text not null default 'USD',
  cost_type   text not null,                  -- fixed|variable|transactional|annual|one_time
  period      text not null,                  -- monthly|annual|one_time
  description text,
  start_date  date,
  end_date    date,
  created_at  timestamptz not null default now()
);
create index if not exists idx_costs_user on costs(user_id);

-- ---------------------------------------------------------------------------
-- ownership (Ownership Center — asset control checklist)
-- ---------------------------------------------------------------------------
create table if not exists ownership (
  id          text primary key,
  user_id     text not null references users(user_id) on delete cascade,
  project_id  text not null references projects(id) on delete cascade,
  asset       text not null,                  -- repository|domain|database|...
  status      text not null,                  -- owned|third_party|not_verified|...
  owner       text,
  account_url text,
  notes       text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  unique (user_id, project_id, asset)
);
create index if not exists idx_ownership_project on ownership(project_id);

-- ---------------------------------------------------------------------------
-- documents (PRD Center — markdown docs per project)
-- ---------------------------------------------------------------------------
create table if not exists documents (
  id          text primary key,
  user_id     text not null references users(user_id) on delete cascade,
  project_id  text not null references projects(id) on delete cascade,
  doc_type    text not null,                  -- prd|architecture|security|qa|...
  content     text not null,
  version     text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index if not exists idx_documents_project on documents(project_id);

-- ---------------------------------------------------------------------------
-- decisions (project decision log)
-- ---------------------------------------------------------------------------
create table if not exists decisions (
  id          text primary key,
  user_id     text not null references users(user_id) on delete cascade,
  project_id  text not null references projects(id) on delete cascade,
  title       text not null,
  decision    text not null,
  rationale   text,
  created_at  timestamptz not null default now()
);
create index if not exists idx_decisions_project on decisions(project_id);

-- ---------------------------------------------------------------------------
-- evidence (QA & Security evidence — DETECTED vs VERIFIED)
-- ---------------------------------------------------------------------------
create table if not exists evidence (
  id          text primary key,
  user_id     text not null references users(user_id) on delete cascade,
  project_id  text not null references projects(id) on delete cascade,
  category    text not null,                  -- qa|security
  claim       text not null,
  status      text not null,                  -- detected|verified|not_verified
  evidence    text,
  source      text,
  verified_at timestamptz,
  created_at  timestamptz not null default now()
);
create index if not exists idx_evidence_project on evidence(project_id);

-- ---------------------------------------------------------------------------
-- ideas (Idea Pipeline)
-- ---------------------------------------------------------------------------
create table if not exists ideas (
  id          text primary key,
  user_id     text not null references users(user_id) on delete cascade,
  title       text not null,
  description text,
  status      text not null default 'idea',   -- idea|validating|validated|archived
  created_at  timestamptz not null default now()
);
create index if not exists idx_ideas_user on ideas(user_id);

-- ---------------------------------------------------------------------------
-- launch_checklist (Launch Center)
-- ---------------------------------------------------------------------------
create table if not exists launch_checklist (
  id          text primary key,
  user_id     text not null references users(user_id) on delete cascade,
  project_id  text not null references projects(id) on delete cascade,
  item        text not null,
  done        boolean not null default false,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index if not exists idx_launch_project on launch_checklist(project_id);

-- ============================================================================
-- NOTES
-- * Row Level Security: Option A keeps auth in FastAPI (service role key used
--   server-side), so RLS is NOT required for correctness — user_id filtering is
--   enforced in application code exactly as it is today with Mongo. If you later
--   move to Supabase Auth + direct PostgREST from the browser, enable RLS then.
-- * All foreign keys use ON DELETE CASCADE / SET NULL to mirror today's behavior
--   where deleting a user/project removes dependent rows.
-- ============================================================================
