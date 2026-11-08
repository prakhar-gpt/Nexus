-- Nexus schema for database nexus_db.
-- Week 1 created workspaces, uploads, and sales_clean.
-- Week 2 adds column_mapping and quarantine.
-- Week 3 adds runs, feedback, and eval_results. documents and chunks are still absent.

CREATE TABLE IF NOT EXISTS workspaces (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS uploads (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    workspace_id bigint NOT NULL REFERENCES workspaces (id),
    original_name text NOT NULL,
    stored_name text NOT NULL,
    sha256 text NOT NULL,
    size bigint NOT NULL,
    status text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sales_clean (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    workspace_id bigint NOT NULL REFERENCES workspaces (id),
    upload_id bigint NOT NULL REFERENCES uploads (id),
    order_date date NOT NULL,
    customer_id text NOT NULL,
    product_id text NOT NULL,
    quantity integer,
    revenue numeric NOT NULL,
    unit_price numeric,
    discount_pct numeric,
    cost numeric,
    profit numeric,
    segment text NOT NULL,
    region text NOT NULL,
    category text NOT NULL,
    sub_category text NOT NULL,
    channel text
);

CREATE INDEX IF NOT EXISTS sales_clean_workspace_id_idx
    ON sales_clean (workspace_id);

COMMENT ON TABLE sales_clean IS
    'Canonical sales table. run_sql reads this table only.';
COMMENT ON COLUMN sales_clean.quantity IS
    'Nullable: the checked-in Superstore extract has no quantity.';
COMMENT ON COLUMN sales_clean.unit_price IS
    'Nullable: the checked-in Superstore extract has no unit price.';
COMMENT ON COLUMN sales_clean.discount_pct IS
    'Nullable: the checked-in Superstore extract has no discount.';
COMMENT ON COLUMN sales_clean.cost IS
    'Nullable. Margin questions are refused when cost is absent.';
COMMENT ON COLUMN sales_clean.profit IS
    'Nullable. Margin questions are refused when profit is absent.';
COMMENT ON COLUMN sales_clean.channel IS
    'Nullable: the checked-in Superstore extract has no channel.';

CREATE TABLE IF NOT EXISTS column_mapping (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    upload_id bigint NOT NULL REFERENCES uploads (id),
    source_column text NOT NULL,
    canonical_column text,
    confidence numeric,
    method text NOT NULL,
    confirmed_by_user boolean NOT NULL DEFAULT false
);

CREATE INDEX IF NOT EXISTS column_mapping_upload_id_idx
    ON column_mapping (upload_id);

CREATE TABLE IF NOT EXISTS quarantine (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    upload_id bigint NOT NULL REFERENCES uploads (id),
    row_number integer NOT NULL,
    reason text NOT NULL,
    raw_json jsonb NOT NULL
);

CREATE INDEX IF NOT EXISTS quarantine_upload_id_idx
    ON quarantine (upload_id);

ALTER TABLE sales_clean ALTER COLUMN customer_id DROP NOT NULL;
ALTER TABLE sales_clean ALTER COLUMN product_id DROP NOT NULL;
ALTER TABLE sales_clean ALTER COLUMN revenue DROP NOT NULL;
ALTER TABLE sales_clean ALTER COLUMN segment DROP NOT NULL;
ALTER TABLE sales_clean ALTER COLUMN region DROP NOT NULL;
ALTER TABLE sales_clean ALTER COLUMN category DROP NOT NULL;
ALTER TABLE sales_clean ALTER COLUMN sub_category DROP NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'sales_clean_identifier_chk'
    ) THEN
        ALTER TABLE sales_clean
            ADD CONSTRAINT sales_clean_identifier_chk
            CHECK (customer_id IS NOT NULL OR product_id IS NOT NULL);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'sales_clean_measure_chk'
    ) THEN
        ALTER TABLE sales_clean
            ADD CONSTRAINT sales_clean_measure_chk
            CHECK (revenue IS NOT NULL OR quantity IS NOT NULL);
    END IF;
END
$$;

-- Week 3. runs.workspace_id is not in the v2 column list. Decision 20.

CREATE TABLE IF NOT EXISTS runs (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    workspace_id bigint NOT NULL REFERENCES workspaces (id),
    question text NOT NULL,
    plan text,
    sql_list text,
    answer text,
    checker_result jsonb,
    latency_ms integer,
    tokens integer,
    cost numeric,
    model text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS runs_workspace_id_idx ON runs (workspace_id);

CREATE TABLE IF NOT EXISTS feedback (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id bigint NOT NULL REFERENCES runs (id),
    rating text NOT NULL,
    reason text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS eval_results (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    eval_run_id text NOT NULL,
    question_id text NOT NULL,
    passed boolean NOT NULL,
    metrics_json jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
