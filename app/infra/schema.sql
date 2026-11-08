-- Nexus Week 1 schema for database nexus_db.
-- Tables required to load sales_clean with the v2 foreign keys.
-- The other six tables are not created in this step.

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
