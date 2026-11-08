-- Week 4 idempotent migration for existing nexus_db databases.
-- Safe to re-run: every statement uses IF NOT EXISTS or DO $$ guards.
-- For fresh installs, schema.sql is authoritative; this file is for existing DBs.

-- 1. Add attributes JSONB to sales_clean (stores unmapped columns).
ALTER TABLE sales_clean ADD COLUMN IF NOT EXISTS attributes jsonb NOT NULL DEFAULT '{}';

-- 2. GIN index for JSONB attribute key/value lookups.
CREATE INDEX IF NOT EXISTS sales_clean_attributes_gin ON sales_clean USING gin(attributes);

-- 3. Per-upload attribute schema table (key, inferred type, null rate, samples).
CREATE TABLE IF NOT EXISTS upload_attribute_schema (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    upload_id  bigint NOT NULL REFERENCES uploads (id),
    key        text NOT NULL,
    inferred_type text NOT NULL,
    null_rate  numeric NOT NULL DEFAULT 0,
    sample_values jsonb NOT NULL DEFAULT '[]',
    UNIQUE (upload_id, key)
);

CREATE INDEX IF NOT EXISTS upload_attribute_schema_upload_id_idx
    ON upload_attribute_schema (upload_id);

-- 4. Add capabilities JSONB to uploads (revenue/trend/margin/discount/customer flags).
ALTER TABLE uploads ADD COLUMN IF NOT EXISTS capabilities jsonb;

-- 5. Add python_results JSONB to runs (stores run_python output per turn).
ALTER TABLE runs ADD COLUMN IF NOT EXISTS python_results jsonb;

-- 6. Grant nexus_reader SELECT on the new table.
--    sales_clean.attributes is on an already-granted table; no extra grant needed.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexus_reader') THEN
        EXECUTE 'GRANT SELECT ON TABLE upload_attribute_schema TO nexus_reader';
    END IF;
END
$$;

-- 7. Grant nexus_writer on the new table and new sequences.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexus_writer') THEN
        EXECUTE 'GRANT SELECT, INSERT, UPDATE ON TABLE upload_attribute_schema TO nexus_writer';
        EXECUTE 'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nexus_writer';
    END IF;
END
$$;

COMMENT ON COLUMN sales_clean.attributes IS
    'Unmapped source columns stored as {snake_case_key: raw_value}. '
    'Cast expressions are exposed by get_schema.';
COMMENT ON TABLE upload_attribute_schema IS
    'Per-upload inventory of attributes keys: inferred type, null rate, sample values.';
COMMENT ON COLUMN uploads.capabilities IS
    '{revenue,trend,margin,discount,customer}: bool flags plus reason strings.';
COMMENT ON COLUMN runs.python_results IS
    'Labelled numeric results from run_python, keyed by label.';

