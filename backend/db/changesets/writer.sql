-- Load role for ingestion. The password is applied outside this file.

GRANT CONNECT ON DATABASE nexus_db TO nexus_writer;
GRANT USAGE ON SCHEMA public TO nexus_writer;
GRANT USAGE, CREATE ON SCHEMA user_data TO nexus_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO nexus_writer;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nexus_writer;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name = 'sales_clean' AND table_type = 'BASE TABLE'
    ) THEN
        DROP POLICY IF EXISTS sales_clean_writer_all ON public.sales_clean;
        CREATE POLICY sales_clean_writer_all ON public.sales_clean
            FOR ALL
            TO nexus_writer
            USING (true)
            WITH CHECK (true);
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'user_data' AND table_name = 'ds_superstore'
    ) THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON user_data.ds_superstore TO nexus_writer;
        DROP POLICY IF EXISTS ds_superstore_writer_all ON user_data.ds_superstore;
        CREATE POLICY ds_superstore_writer_all ON user_data.ds_superstore
            FOR ALL
            TO nexus_writer
            USING (true)
            WITH CHECK (true);
    END IF;
END $$;
