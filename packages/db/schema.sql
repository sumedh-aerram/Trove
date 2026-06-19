-- Trove schema
-- PostgreSQL + pgvector. Supabase-compatible (uses gen_random_uuid via pgcrypto).

create extension if not exists vector;
create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- profiles
-- ---------------------------------------------------------------------------
create table if not exists profiles (
  id                uuid primary key default gen_random_uuid(),
  username          text unique not null,
  display_name      text,
  bio               text,
  github_url        text,
  website_url       text,
  credibility_score double precision default 0,
  created_at        timestamptz default now()
);

-- ---------------------------------------------------------------------------
-- artifacts (the core BuildArtifact object)
-- ---------------------------------------------------------------------------
create table if not exists artifacts (
  id                uuid primary key default gen_random_uuid(),
  title             text not null,
  slug              text unique not null,
  source_type       text not null,
  artifact_type     text not null,
  source_url        text not null,
  canonical_url     text unique,
  author_name       text,
  author_url        text,

  raw_text          text,
  clean_text        text,
  summary           text,
  what_it_helps_build text,
  technical_core    text,
  practical_use_case text,
  how_to_remix      text,
  implementation_steps jsonb default '[]',
  setup_commands    jsonb default '[]',

  tags              text[] default '{}',
  domains           text[] default '{}',
  tools             text[] default '{}',
  languages         text[] default '{}',
  frameworks        text[] default '{}',
  apis              text[] default '{}',
  models            text[] default '{}',

  has_code          boolean default false,
  has_demo          boolean default false,
  has_docs          boolean default false,
  has_paper         boolean default false,
  has_license       boolean default false,
  license           text,

  difficulty        text default 'unknown',
  estimated_time_to_integrate text,

  published_at      timestamptz,
  first_seen_at     timestamptz default now(),
  last_crawled_at   timestamptz,

  quality_score     double precision default 0,
  remixability_score double precision default 0,
  applicability_score double precision default 0,
  underground_score double precision default 0,
  hype_risk_score   double precision default 0,
  popularity_score  double precision default 0,

  search_vector     tsvector,
  embedding         vector(384),

  created_at        timestamptz default now(),
  updated_at        timestamptz default now()
);

-- ---------------------------------------------------------------------------
-- user_posts (submissions + moderation state)
-- ---------------------------------------------------------------------------
create table if not exists user_posts (
  id                uuid primary key default gen_random_uuid(),
  author_id         uuid references profiles(id),
  artifact_id       uuid references artifacts(id),
  status            text default 'pending',
  moderation_reason text,
  quality_explanation text,
  hype_explanation  text,
  created_at        timestamptz default now()
);

-- ---------------------------------------------------------------------------
-- artifact_sources (provenance / multi-source merge)
-- ---------------------------------------------------------------------------
create table if not exists artifact_sources (
  id                uuid primary key default gen_random_uuid(),
  artifact_id       uuid references artifacts(id),
  source_name       text not null,
  source_url        text not null,
  metadata          jsonb default '{}',
  created_at        timestamptz default now()
);

-- ---------------------------------------------------------------------------
-- stars (user saves an artifact)
-- ---------------------------------------------------------------------------
create table if not exists stars (
  user_id           uuid references profiles(id),
  artifact_id       uuid references artifacts(id),
  created_at        timestamptz default now(),
  primary key (user_id, artifact_id)
);

-- ---------------------------------------------------------------------------
-- search_events (analytics)
-- ---------------------------------------------------------------------------
create table if not exists search_events (
  id                uuid primary key default gen_random_uuid(),
  user_id           uuid references profiles(id),
  query             text not null,
  project_context   jsonb default '{}',
  clicked_artifact_id uuid,
  saved_artifact_id uuid,
  created_at        timestamptz default now()
);

-- ---------------------------------------------------------------------------
-- crawl_runs (crawler bookkeeping)
-- ---------------------------------------------------------------------------
create table if not exists crawl_runs (
  id                uuid primary key default gen_random_uuid(),
  source_type       text not null,
  query             text,
  status            text default 'running',
  artifacts_found   integer default 0,
  artifacts_inserted integer default 0,
  error             text,
  started_at        timestamptz default now(),
  finished_at       timestamptz
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------
create index if not exists idx_artifacts_search_vector on artifacts using gin (search_vector);

-- HNSW vector index for cosine similarity search.
create index if not exists idx_artifacts_embedding on artifacts
  using hnsw (embedding vector_cosine_ops);

create index if not exists idx_artifacts_tags       on artifacts using gin (tags);
create index if not exists idx_artifacts_tools      on artifacts using gin (tools);
create index if not exists idx_artifacts_frameworks on artifacts using gin (frameworks);
create index if not exists idx_artifacts_languages  on artifacts using gin (languages);

create index if not exists idx_artifacts_created_at on artifacts (created_at desc);
create index if not exists idx_artifacts_artifact_type on artifacts (artifact_type);
create index if not exists idx_artifacts_source_type on artifacts (source_type);
create index if not exists idx_artifacts_quality_score on artifacts (quality_score desc);
create index if not exists idx_artifacts_remixability_score on artifacts (remixability_score desc);
create index if not exists idx_artifacts_underground_score on artifacts (underground_score desc);

-- ---------------------------------------------------------------------------
-- search_vector trigger (english config)
-- Weights: title (A) > summary/what_it_helps_build (B) > technical/use case (C)
--          > arrays (D)
-- ---------------------------------------------------------------------------
create or replace function artifacts_search_vector_update() returns trigger as $$
begin
  new.search_vector :=
      setweight(to_tsvector('english', coalesce(new.title, '')), 'A')
    || setweight(to_tsvector('english', coalesce(new.summary, '')), 'B')
    || setweight(to_tsvector('english', coalesce(new.what_it_helps_build, '')), 'B')
    || setweight(to_tsvector('english', coalesce(new.technical_core, '')), 'C')
    || setweight(to_tsvector('english', coalesce(new.practical_use_case, '')), 'C')
    || setweight(to_tsvector('english', coalesce(new.how_to_remix, '')), 'C')
    || setweight(to_tsvector('english', coalesce(array_to_string(new.tags, ' '), '')), 'B')
    || setweight(to_tsvector('english', coalesce(array_to_string(new.tools, ' '), '')), 'B')
    || setweight(to_tsvector('english', coalesce(array_to_string(new.frameworks, ' '), '')), 'B')
    || setweight(to_tsvector('english', coalesce(array_to_string(new.languages, ' '), '')), 'C')
    || setweight(to_tsvector('english', coalesce(array_to_string(new.apis, ' '), '')), 'C')
    || setweight(to_tsvector('english', coalesce(array_to_string(new.models, ' '), '')), 'C');
  new.updated_at := now();
  return new;
end
$$ language plpgsql;

drop trigger if exists trg_artifacts_search_vector on artifacts;
create trigger trg_artifacts_search_vector
  before insert or update on artifacts
  for each row execute function artifacts_search_vector_update();
