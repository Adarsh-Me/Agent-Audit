-- AgentAudit DDL — authoritative per SCHEMA §6 (Postgres 16).
-- SQLite dev fallback derives from app/db/models.py (sync enforced by tests).

CREATE TABLE merchants (
  id               UUID PRIMARY KEY,
  name             TEXT NOT NULL,
  gmv_monthly_inr  INTEGER,
  aov_inr          INTEGER,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE catalogs (
  id                 UUID PRIMARY KEY,
  merchant_id        UUID NOT NULL REFERENCES merchants(id),
  source             TEXT NOT NULL CHECK (source IN ('demo','upload','mirror')),  -- SC-2
  parent_catalog_id  UUID REFERENCES catalogs(id),                                -- SC-2: mirror → original
  version            INTEGER NOT NULL DEFAULT 1,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE products (
  id                   UUID PRIMARY KEY,
  catalog_id           UUID NOT NULL REFERENCES catalogs(id),
  sku                  TEXT NOT NULL,
  title                TEXT NOT NULL,
  price_inr            INTEGER,              -- true price; null only for malformed uploads
  description          TEXT,
  image_url            TEXT,
  page_url             TEXT,
  tier                 TEXT NOT NULL CHECK (tier IN ('rich','medium','starved','unknown')),
  structured_data      JSONB NOT NULL DEFAULT '{}',
  legibility_composite REAL,
  UNIQUE (catalog_id, sku)
);

CREATE TABLE runs (
  id            UUID PRIMARY KEY,
  catalog_id    UUID NOT NULL REFERENCES catalogs(id),
  parent_run_id UUID REFERENCES runs(id),                                          -- SC-4
  type          TEXT NOT NULL CHECK (type IN ('audit','rerun')),
  status        TEXT NOT NULL CHECK (status IN ('queued','running','done','failed','partial')),
  models        JSONB NOT NULL,        -- §3.4 snapshot
  seeds         JSONB NOT NULL,        -- §3.4 snapshot
  cost_usd      REAL NOT NULL DEFAULT 0,
  trials_total  INTEGER NOT NULL DEFAULT 220,                                       -- SC-6
  abort_reason  TEXT,                -- human-readable partial/failed cause
  started_at    TIMESTAMPTZ,
  completed_at  TIMESTAMPTZ
);

CREATE TABLE trials (
  id               UUID PRIMARY KEY,
  run_id           UUID NOT NULL REFERENCES runs(id),
  model            TEXT NOT NULL,       -- §2.3 engine id
  model_version    TEXT NOT NULL,       -- pinned snapshot
  tier             TEXT NOT NULL CHECK (tier IN ('bulk','flagship')),               -- SC-6
  persona_id       TEXT NOT NULL,       -- P01..P20
  condition        TEXT NOT NULL,       -- §2.2 codes
  seed             INTEGER NOT NULL,    -- §3.3.3 LLM seed
  presented_order  JSONB NOT NULL,      -- array[40] of sku, presented order
  choice           TEXT,                -- sku | NULL; semantics §3.3.2
  reason           TEXT,
  latency_ms       INTEGER,
  prompt_hash      TEXT NOT NULL,
  from_cache       BOOLEAN NOT NULL DEFAULT false,                                  -- SC-6
  null_allowed     BOOLEAN NOT NULL,
  parse_ok         BOOLEAN NOT NULL DEFAULT true,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (parse_ok = false OR choice IS NOT NULL OR null_allowed = true)             -- C-2
);
CREATE INDEX idx_trials_run  ON trials(run_id);
CREATE INDEX idx_trials_hash ON trials(prompt_hash);

CREATE TABLE response_cache (
  prompt_hash    TEXT NOT NULL,
  model_version  TEXT NOT NULL,
  response       JSONB NOT NULL,        -- {"product_id": …|null, "reason": …, "raw": …}
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (prompt_hash, model_version)
);

CREATE TABLE metrics (
  id        UUID PRIMARY KEY,
  run_id    UUID NOT NULL REFERENCES runs(id),
  key       TEXT NOT NULL,              -- §2.4 namespace
  value     REAL,
  ci_low    REAL,
  ci_high   REAL,
  payload   JSONB,
  UNIQUE (run_id, key)
);

CREATE TABLE remediations (
  id          UUID PRIMARY KEY,
  run_id      UUID NOT NULL REFERENCES runs(id),
  product_id  UUID NOT NULL REFERENCES products(id),   -- original catalog's product
  fixes       JSONB NOT NULL,             -- array of §3.8 Fix objects
  status      TEXT NOT NULL DEFAULT 'pending'
              CHECK (status IN ('pending','approved','rejected')),                   -- SC-6
  reviewed_by TEXT,
  applied_at  TIMESTAMPTZ
);

CREATE TABLE payments (
  id               UUID PRIMARY KEY,
  run_id           UUID NOT NULL REFERENCES runs(id),
  razorpay_link_id TEXT UNIQUE,
  amount_inr       INTEGER NOT NULL,
  status           TEXT NOT NULL DEFAULT 'created'
                   CHECK (status IN ('created','captured','failed')),
  captured_at      TIMESTAMPTZ,
  idempotency_key  TEXT NOT NULL UNIQUE          -- "agentaudit:{run_id}:{sku}"
);

CREATE TABLE webhook_events (
  id           UUID PRIMARY KEY,
  source       TEXT NOT NULL CHECK (source IN ('razorpay','merchant_onboarding')),
  type         TEXT NOT NULL,             -- §9 accepted types
  entity_key   TEXT NOT NULL,             -- SC-1: extractor-defined dedupe key
  payload      JSONB NOT NULL,
  processed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (source, type, entity_key)                                             -- SC-1
);
