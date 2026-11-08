-- Load role for ingestion. The password is applied outside this file.

GRANT CONNECT ON DATABASE nexus_db TO nexus_writer;
GRANT USAGE ON SCHEMA public TO nexus_writer;
GRANT SELECT, INSERT, UPDATE ON
    workspaces,
    uploads,
    column_mapping,
    sales_clean,
    quarantine
TO nexus_writer;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nexus_writer;

DROP POLICY IF EXISTS sales_clean_writer_all ON sales_clean;
CREATE POLICY sales_clean_writer_all ON sales_clean
    FOR ALL
    TO nexus_writer
    USING (true)
    WITH CHECK (true);
