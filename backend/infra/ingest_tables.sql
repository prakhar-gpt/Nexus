-- Week 2 tables and the nullable measures the domain-fit rule allows.

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
