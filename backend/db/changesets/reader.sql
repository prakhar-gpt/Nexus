-- Read-only access for run_sql. The role itself is created by db.ensure_reader
-- so its password is never stored in this file.

GRANT CONNECT ON DATABASE nexus_db TO nexus_reader;
GRANT USAGE ON SCHEMA public TO nexus_reader;
GRANT USAGE ON SCHEMA user_data TO nexus_reader;
GRANT SELECT ON TABLE sales_clean TO nexus_reader;
ALTER ROLE nexus_reader SET search_path = user_data, public;

ALTER TABLE sales_clean ENABLE ROW LEVEL SECURITY;
ALTER TABLE sales_clean FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS sales_clean_reader_workspace ON sales_clean;
CREATE POLICY sales_clean_reader_workspace ON sales_clean
    FOR SELECT
    TO nexus_reader
    USING (
        workspace_id = current_setting('app.workspace_id', true)::bigint
    );
