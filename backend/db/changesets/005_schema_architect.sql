-- 005_schema_architect.sql: Schema Architect catalog and user_data schema
-- Safe to re-run: uses IF NOT EXISTS and DO $$ guards.

-- 1. Create dedicated schema for dynamically approved custom datasets
CREATE SCHEMA IF NOT EXISTS user_data;

-- 2. Datasets catalog table (tracks approved tables per workspace)
CREATE TABLE IF NOT EXISTS datasets (
    id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    workspace_id       bigint NOT NULL REFERENCES workspaces (id),
    upload_id          bigint NOT NULL REFERENCES uploads (id),
    table_name         text NOT NULL UNIQUE,
    table_label        text NOT NULL,
    grain              text NOT NULL,
    grain_key_columns  jsonb NOT NULL DEFAULT '[]',
    header_hash        text,
    approved_by        text NOT NULL DEFAULT 'user',
    approved_at        timestamptz NOT NULL DEFAULT now(),
    proposal_json      jsonb NOT NULL DEFAULT '{}',
    row_count          bigint NOT NULL DEFAULT 0,
    created_at         timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS datasets_workspace_id_idx ON datasets (workspace_id);
CREATE INDEX IF NOT EXISTS datasets_header_hash_idx ON datasets (workspace_id, header_hash);

-- 3. Dataset columns catalog table
CREATE TABLE IF NOT EXISTS dataset_columns (
    id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_id         bigint NOT NULL REFERENCES datasets (id) ON DELETE CASCADE,
    column_name        text NOT NULL,
    source_name        text NOT NULL,
    type               text NOT NULL,
    role               text NOT NULL,
    description        text NOT NULL,
    unit               text,
    nullable           boolean NOT NULL DEFAULT true,
    null_rate          numeric NOT NULL DEFAULT 0,
    created_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (dataset_id, column_name)
);

CREATE INDEX IF NOT EXISTS dataset_columns_dataset_id_idx ON dataset_columns (dataset_id);

-- 4. Schema proposals storage on uploads table if not present
ALTER TABLE uploads ADD COLUMN IF NOT EXISTS schema_proposal jsonb;
ALTER TABLE uploads ADD COLUMN IF NOT EXISTS custom_table_name text;

-- 5. Architect runs history table (for auditing and diff tracking)
CREATE TABLE IF NOT EXISTS architect_runs (
    id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    upload_id          bigint NOT NULL REFERENCES uploads (id),
    workspace_id       bigint NOT NULL REFERENCES workspaces (id),
    model              text NOT NULL,
    latency_ms         integer NOT NULL DEFAULT 0,
    tool_calls         jsonb NOT NULL DEFAULT '[]',
    proposal           jsonb NOT NULL DEFAULT '{}',
    approved_diff      jsonb,
    created_at         timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS architect_runs_upload_id_idx ON architect_runs (upload_id);

-- 6. Setup roles and permissions
-- nexus_ingest role for creating and populating tables strictly in user_data schema
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexus_ingest') THEN
        CREATE ROLE nexus_ingest LOGIN PASSWORD 'nexus_ingest_password';
    END IF;
END
$$;

-- Grant permissions for nexus_ingest:
GRANT USAGE, CREATE ON SCHEMA user_data TO nexus_ingest;
GRANT USAGE ON SCHEMA public TO nexus_ingest;
GRANT SELECT, INSERT, UPDATE ON TABLE datasets, dataset_columns, uploads, quarantine, architect_runs TO nexus_ingest;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nexus_ingest;

-- Fallback grants for nexus_writer so existing services can also write to catalogs:
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexus_writer') THEN
        GRANT USAGE, CREATE ON SCHEMA user_data TO nexus_writer;
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE datasets, dataset_columns, architect_runs TO nexus_writer;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nexus_writer;
    END IF;
END
$$;

-- Grant nexus_reader USAGE on schema user_data and SELECT on datasets catalog
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexus_reader') THEN
        GRANT USAGE ON SCHEMA user_data TO nexus_reader;
        GRANT SELECT ON TABLE datasets, dataset_columns TO nexus_reader;
    END IF;
END
$$;
