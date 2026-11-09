-- Read-only access for run_sql. The role itself is created by db.ensure_reader
-- so its password is never stored in this file.

GRANT CONNECT ON DATABASE nexus_db TO nexus_reader;
GRANT USAGE ON SCHEMA public TO nexus_reader;
GRANT USAGE ON SCHEMA user_data TO nexus_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO nexus_reader;
ALTER ROLE nexus_reader SET search_path = user_data, public;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name = 'sales_clean' AND table_type = 'BASE TABLE'
    ) THEN
        ALTER TABLE public.sales_clean ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.sales_clean FORCE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS sales_clean_reader_workspace ON public.sales_clean;
        CREATE POLICY sales_clean_reader_workspace ON public.sales_clean
            FOR SELECT
            TO nexus_reader
            USING (
                workspace_id = (NULLIF(current_setting('app.workspace_id', true), ''))::uuid
            );
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'user_data' AND table_name = 'ds_superstore'
    ) THEN
        ALTER TABLE user_data.ds_superstore ENABLE ROW LEVEL SECURITY;
        ALTER TABLE user_data.ds_superstore FORCE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS ds_superstore_reader ON user_data.ds_superstore;
        CREATE POLICY ds_superstore_reader ON user_data.ds_superstore
            FOR SELECT
            TO nexus_reader
            USING (
                workspace_id = (NULLIF(current_setting('app.workspace_id', true), ''))::uuid
            );
        GRANT SELECT ON user_data.ds_superstore TO nexus_reader;
    END IF;
END $$;
