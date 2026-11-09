-- Changeset 008: Users table, workspace membership, and full UUID primary/foreign keys migration.
-- Idempotent and safe to run on existing databases or fresh installs.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Create users table
CREATE TABLE IF NOT EXISTS users (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email      text UNIQUE NOT NULL,
    name       text NOT NULL,
    role       text NOT NULL DEFAULT 'Consulting Analyst',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Seed default user
INSERT INTO users (id, email, name, role)
VALUES ('00000000-0000-0000-0000-000000000001'::uuid, 'prakhar@nexus.ai', 'Prakhar Gupta', 'Consulting Analyst')
ON CONFLICT (email) DO NOTHING;

-- 2. Add owner_id to workspaces
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS owner_id uuid REFERENCES users(id) ON DELETE SET NULL;

-- 3. Create workspace_members table
CREATE TABLE IF NOT EXISTS workspace_members (
    workspace_id uuid NOT NULL,
    user_id      uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role         text NOT NULL DEFAULT 'owner',
    joined_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, user_id)
);

-- 4. Convert existing tables from bigint to uuid if not yet converted
DO $$
DECLARE
    r RECORD;
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'workspaces' AND column_name = 'id' AND data_type != 'uuid'
    ) THEN
        -- Drop policies that depend on workspace_id before altering column types
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'threads') THEN
            DROP POLICY IF EXISTS threads_reader_workspace ON threads;
            DROP POLICY IF EXISTS threads_writer_all ON threads;
        END IF;
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'user_data' AND table_name = 'ds_superstore') THEN
            DROP POLICY IF EXISTS ds_superstore_reader ON user_data.ds_superstore;
        END IF;
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'sales_clean' AND table_type = 'BASE TABLE') THEN
            DROP POLICY IF EXISTS sales_clean_reader_workspace ON public.sales_clean;
        END IF;

        -- Drop ALL foreign keys referencing workspaces(id) across all tables
        FOR r IN (
            SELECT tc.table_schema, tc.table_name, tc.constraint_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND ccu.table_name = 'workspaces'
              AND ccu.column_name = 'id'
        ) LOOP
            EXECUTE format('ALTER TABLE %I.%I DROP CONSTRAINT IF EXISTS %I;', r.table_schema, r.table_name, r.constraint_name);
        END LOOP;

        -- Drop ALL foreign keys referencing uploads(id) across all tables
        FOR r IN (
            SELECT tc.table_schema, tc.table_name, tc.constraint_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND ccu.table_name = 'uploads'
              AND ccu.column_name = 'id'
        ) LOOP
            EXECUTE format('ALTER TABLE %I.%I DROP CONSTRAINT IF EXISTS %I;', r.table_schema, r.table_name, r.constraint_name);
        END LOOP;

        -- Drop ALL foreign keys referencing datasets(id) across all tables
        FOR r IN (
            SELECT tc.table_schema, tc.table_name, tc.constraint_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND ccu.table_name = 'datasets'
              AND ccu.column_name = 'id'
        ) LOOP
            EXECUTE format('ALTER TABLE %I.%I DROP CONSTRAINT IF EXISTS %I;', r.table_schema, r.table_name, r.constraint_name);
        END LOOP;

        -- Drop ALL foreign keys referencing runs(id) across all tables
        FOR r IN (
            SELECT tc.table_schema, tc.table_name, tc.constraint_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND ccu.table_name = 'runs'
              AND ccu.column_name = 'id'
        ) LOOP
            EXECUTE format('ALTER TABLE %I.%I DROP CONSTRAINT IF EXISTS %I;', r.table_schema, r.table_name, r.constraint_name);
        END LOOP;

        -- 1. Convert workspaces
        ALTER TABLE workspaces ALTER COLUMN id DROP IDENTITY IF EXISTS;
        ALTER TABLE workspaces ALTER COLUMN id TYPE uuid USING lpad(to_hex(id), 32, '0')::uuid;
        ALTER TABLE workspaces ALTER COLUMN id SET DEFAULT gen_random_uuid();

        -- 2. Convert uploads
        ALTER TABLE uploads ALTER COLUMN id DROP IDENTITY IF EXISTS;
        ALTER TABLE uploads ALTER COLUMN id TYPE uuid USING lpad(to_hex(id), 32, '0')::uuid;
        ALTER TABLE uploads ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE uploads ALTER COLUMN workspace_id TYPE uuid USING lpad(to_hex(workspace_id), 32, '0')::uuid;

        -- 3. Convert datasets & dataset_columns
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'datasets') THEN
            ALTER TABLE datasets ALTER COLUMN id DROP IDENTITY IF EXISTS;
            ALTER TABLE datasets ALTER COLUMN id TYPE uuid USING lpad(to_hex(id), 32, '0')::uuid;
            ALTER TABLE datasets ALTER COLUMN id SET DEFAULT gen_random_uuid();
            ALTER TABLE datasets ALTER COLUMN workspace_id TYPE uuid USING lpad(to_hex(workspace_id), 32, '0')::uuid;
            ALTER TABLE datasets ALTER COLUMN upload_id TYPE uuid USING lpad(to_hex(upload_id), 32, '0')::uuid;
        END IF;

        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'dataset_columns') THEN
            ALTER TABLE dataset_columns ALTER COLUMN id DROP IDENTITY IF EXISTS;
            ALTER TABLE dataset_columns ALTER COLUMN id TYPE uuid USING lpad(to_hex(id), 32, '0')::uuid;
            ALTER TABLE dataset_columns ALTER COLUMN id SET DEFAULT gen_random_uuid();
            ALTER TABLE dataset_columns ALTER COLUMN dataset_id TYPE uuid USING lpad(to_hex(dataset_id), 32, '0')::uuid;
        END IF;

        -- 4. Convert threads
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'threads') THEN
            ALTER TABLE threads ALTER COLUMN workspace_id TYPE uuid USING lpad(to_hex(workspace_id), 32, '0')::uuid;
            ALTER TABLE threads ALTER COLUMN selected_dataset_ids TYPE text[] USING selected_dataset_ids::text[];
        END IF;

        -- 5. Convert runs
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'runs') THEN
            ALTER TABLE runs ALTER COLUMN id DROP IDENTITY IF EXISTS;
            ALTER TABLE runs ALTER COLUMN id TYPE uuid USING lpad(to_hex(id), 32, '0')::uuid;
            ALTER TABLE runs ALTER COLUMN id SET DEFAULT gen_random_uuid();
            ALTER TABLE runs ALTER COLUMN workspace_id TYPE uuid USING lpad(to_hex(workspace_id), 32, '0')::uuid;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'runs' AND column_name = 'upload_id') THEN
                ALTER TABLE runs ALTER COLUMN upload_id TYPE uuid USING CASE WHEN upload_id IS NOT NULL THEN lpad(to_hex(upload_id), 32, '0')::uuid ELSE NULL END;
            END IF;
        END IF;

        -- 6. Convert agent_events
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'agent_events') THEN
            ALTER TABLE agent_events ALTER COLUMN id DROP IDENTITY IF EXISTS;
            ALTER TABLE agent_events ALTER COLUMN id TYPE uuid USING lpad(to_hex(id), 32, '0')::uuid;
            ALTER TABLE agent_events ALTER COLUMN id SET DEFAULT gen_random_uuid();
            ALTER TABLE agent_events ALTER COLUMN workspace_id TYPE uuid USING lpad(to_hex(workspace_id), 32, '0')::uuid;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'agent_events' AND column_name = 'run_id') THEN
                ALTER TABLE agent_events ALTER COLUMN run_id TYPE uuid USING CASE WHEN run_id IS NOT NULL THEN lpad(to_hex(run_id), 32, '0')::uuid ELSE NULL END;
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'agent_events' AND column_name = 'upload_id') THEN
                ALTER TABLE agent_events ALTER COLUMN upload_id TYPE uuid USING CASE WHEN upload_id IS NOT NULL THEN lpad(to_hex(upload_id), 32, '0')::uuid ELSE NULL END;
            END IF;
        END IF;

        -- 7. Convert feedback & eval_results
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'feedback') THEN
            ALTER TABLE feedback ALTER COLUMN id DROP IDENTITY IF EXISTS;
            ALTER TABLE feedback ALTER COLUMN id TYPE uuid USING lpad(to_hex(id), 32, '0')::uuid;
            ALTER TABLE feedback ALTER COLUMN id SET DEFAULT gen_random_uuid();
            ALTER TABLE feedback ALTER COLUMN run_id TYPE uuid USING lpad(to_hex(run_id), 32, '0')::uuid;
        END IF;

        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'eval_results') THEN
            ALTER TABLE eval_results ALTER COLUMN id DROP IDENTITY IF EXISTS;
            ALTER TABLE eval_results ALTER COLUMN id TYPE uuid USING lpad(to_hex(id), 32, '0')::uuid;
            ALTER TABLE eval_results ALTER COLUMN id SET DEFAULT gen_random_uuid();
        END IF;

        -- 8. Convert upload_events
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'upload_events') THEN
            ALTER TABLE upload_events ALTER COLUMN id DROP IDENTITY IF EXISTS;
            ALTER TABLE upload_events ALTER COLUMN id TYPE uuid USING lpad(to_hex(id), 32, '0')::uuid;
            ALTER TABLE upload_events ALTER COLUMN id SET DEFAULT gen_random_uuid();
            ALTER TABLE upload_events ALTER COLUMN upload_id TYPE uuid USING lpad(to_hex(upload_id), 32, '0')::uuid;
        END IF;

        -- 9. Convert auxiliary ingest tables
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'quarantine') THEN
            ALTER TABLE quarantine ALTER COLUMN id DROP IDENTITY IF EXISTS;
            ALTER TABLE quarantine ALTER COLUMN id TYPE uuid USING lpad(to_hex(id), 32, '0')::uuid;
            ALTER TABLE quarantine ALTER COLUMN id SET DEFAULT gen_random_uuid();
            ALTER TABLE quarantine ALTER COLUMN upload_id TYPE uuid USING lpad(to_hex(upload_id), 32, '0')::uuid;
        END IF;

        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'column_mapping') THEN
            ALTER TABLE column_mapping ALTER COLUMN id DROP IDENTITY IF EXISTS;
            ALTER TABLE column_mapping ALTER COLUMN id TYPE uuid USING lpad(to_hex(id), 32, '0')::uuid;
            ALTER TABLE column_mapping ALTER COLUMN id SET DEFAULT gen_random_uuid();
            ALTER TABLE column_mapping ALTER COLUMN upload_id TYPE uuid USING lpad(to_hex(upload_id), 32, '0')::uuid;
        END IF;

        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'upload_attribute_schema') THEN
            ALTER TABLE upload_attribute_schema ALTER COLUMN id DROP IDENTITY IF EXISTS;
            ALTER TABLE upload_attribute_schema ALTER COLUMN id TYPE uuid USING lpad(to_hex(id), 32, '0')::uuid;
            ALTER TABLE upload_attribute_schema ALTER COLUMN id SET DEFAULT gen_random_uuid();
            ALTER TABLE upload_attribute_schema ALTER COLUMN upload_id TYPE uuid USING lpad(to_hex(upload_id), 32, '0')::uuid;
        END IF;

        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'architect_runs') THEN
            ALTER TABLE architect_runs ALTER COLUMN id DROP IDENTITY IF EXISTS;
            ALTER TABLE architect_runs ALTER COLUMN id TYPE uuid USING lpad(to_hex(id), 32, '0')::uuid;
            ALTER TABLE architect_runs ALTER COLUMN id SET DEFAULT gen_random_uuid();
            ALTER TABLE architect_runs ALTER COLUMN workspace_id TYPE uuid USING lpad(to_hex(workspace_id), 32, '0')::uuid;
            ALTER TABLE architect_runs ALTER COLUMN upload_id TYPE uuid USING lpad(to_hex(upload_id), 32, '0')::uuid;
        END IF;

        -- 10. Handle user_data.ds_superstore and sales_clean view
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'sales_clean' AND table_type = 'VIEW') THEN
            DROP VIEW IF EXISTS public.sales_clean CASCADE;
        END IF;

        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'user_data' AND table_name = 'ds_superstore') THEN
            ALTER TABLE user_data.ds_superstore ALTER COLUMN id DROP IDENTITY IF EXISTS;
            ALTER TABLE user_data.ds_superstore ALTER COLUMN id TYPE uuid USING lpad(to_hex(id), 32, '0')::uuid;
            ALTER TABLE user_data.ds_superstore ALTER COLUMN id SET DEFAULT gen_random_uuid();
            ALTER TABLE user_data.ds_superstore ALTER COLUMN workspace_id TYPE uuid USING lpad(to_hex(workspace_id), 32, '0')::uuid;
            ALTER TABLE user_data.ds_superstore ALTER COLUMN upload_id TYPE uuid USING lpad(to_hex(upload_id), 32, '0')::uuid;
        END IF;

        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'sales_clean' AND table_type = 'BASE TABLE') THEN
            ALTER TABLE sales_clean ALTER COLUMN id DROP IDENTITY IF EXISTS;
            ALTER TABLE sales_clean ALTER COLUMN id TYPE uuid USING lpad(to_hex(id), 32, '0')::uuid;
            ALTER TABLE sales_clean ALTER COLUMN id SET DEFAULT gen_random_uuid();
            ALTER TABLE sales_clean ALTER COLUMN workspace_id TYPE uuid USING lpad(to_hex(workspace_id), 32, '0')::uuid;
            ALTER TABLE sales_clean ALTER COLUMN upload_id TYPE uuid USING lpad(to_hex(upload_id), 32, '0')::uuid;
        END IF;

        -- Recreate sales_clean view if user_data.ds_superstore exists
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'user_data' AND table_name = 'ds_superstore') THEN
            EXECUTE 'CREATE OR REPLACE VIEW public.sales_clean AS
            SELECT id, workspace_id, upload_id, order_date, customer_id, product_id,
                   quantity, revenue, unit_price, discount_pct, cost, profit,
                   segment, region, category, sub_category, channel, attributes
            FROM user_data.ds_superstore
            WHERE workspace_id = (NULLIF(current_setting(''app.workspace_id'', true), ''''))::uuid';
        END IF;

        -- Re-attach foreign keys
        ALTER TABLE uploads ADD CONSTRAINT uploads_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE;
        ALTER TABLE datasets ADD CONSTRAINT datasets_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE;
        ALTER TABLE datasets ADD CONSTRAINT datasets_upload_id_fkey FOREIGN KEY (upload_id) REFERENCES uploads(id) ON DELETE CASCADE;
        ALTER TABLE dataset_columns ADD CONSTRAINT dataset_columns_dataset_id_fkey FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE;
        ALTER TABLE threads ADD CONSTRAINT threads_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE;
        ALTER TABLE runs ADD CONSTRAINT runs_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE;
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'runs' AND column_name = 'upload_id') THEN
            ALTER TABLE runs ADD CONSTRAINT runs_upload_id_fkey FOREIGN KEY (upload_id) REFERENCES uploads(id) ON DELETE CASCADE;
        END IF;
        ALTER TABLE feedback ADD CONSTRAINT feedback_run_id_fkey FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE;
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'upload_events') THEN
            ALTER TABLE upload_events ADD CONSTRAINT upload_events_upload_id_fkey FOREIGN KEY (upload_id) REFERENCES uploads(id) ON DELETE CASCADE;
        END IF;
        ALTER TABLE quarantine ADD CONSTRAINT quarantine_upload_id_fkey FOREIGN KEY (upload_id) REFERENCES uploads(id) ON DELETE CASCADE;
        ALTER TABLE column_mapping ADD CONSTRAINT column_mapping_upload_id_fkey FOREIGN KEY (upload_id) REFERENCES uploads(id) ON DELETE CASCADE;
        ALTER TABLE upload_attribute_schema ADD CONSTRAINT upload_attribute_schema_upload_id_fkey FOREIGN KEY (upload_id) REFERENCES uploads(id) ON DELETE CASCADE;
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'architect_runs') THEN
            ALTER TABLE architect_runs ADD CONSTRAINT architect_runs_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE;
            ALTER TABLE architect_runs ADD CONSTRAINT architect_runs_upload_id_fkey FOREIGN KEY (upload_id) REFERENCES uploads(id) ON DELETE CASCADE;
        END IF;
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'agent_events') THEN
            ALTER TABLE agent_events ADD CONSTRAINT agent_events_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE;
            ALTER TABLE agent_events ADD CONSTRAINT agent_events_run_id_fkey FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE;
            ALTER TABLE agent_events ADD CONSTRAINT agent_events_upload_id_fkey FOREIGN KEY (upload_id) REFERENCES uploads(id) ON DELETE CASCADE;
        END IF;

        -- Attach foreign key to workspace_members
        ALTER TABLE workspace_members ADD CONSTRAINT workspace_members_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE;

        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'sales_clean' AND table_type = 'BASE TABLE') THEN
            ALTER TABLE sales_clean ADD CONSTRAINT sales_clean_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE;
            ALTER TABLE sales_clean ADD CONSTRAINT sales_clean_upload_id_fkey FOREIGN KEY (upload_id) REFERENCES uploads(id) ON DELETE CASCADE;
        END IF;

        -- Backfill workspace_members for all existing workspaces
        INSERT INTO workspace_members (workspace_id, user_id, role)
        SELECT id, '00000000-0000-0000-0000-000000000001'::uuid, 'owner'
        FROM workspaces
        ON CONFLICT DO NOTHING;

        -- Set owner_id on existing workspaces
        UPDATE workspaces SET owner_id = '00000000-0000-0000-0000-000000000001'::uuid WHERE owner_id IS NULL;
    END IF;
END $$;

-- 5. Re-create RLS policies with ::uuid
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'sales_clean' AND table_type = 'BASE TABLE') THEN
        DROP POLICY IF EXISTS sales_clean_reader_workspace ON public.sales_clean;
        CREATE POLICY sales_clean_reader_workspace ON public.sales_clean
            FOR SELECT TO nexus_reader
            USING (workspace_id = (NULLIF(current_setting('app.workspace_id', true), ''))::uuid);
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'user_data' AND table_name = 'ds_superstore') THEN
        DROP POLICY IF EXISTS ds_superstore_reader ON user_data.ds_superstore;
        CREATE POLICY ds_superstore_reader ON user_data.ds_superstore
            FOR SELECT TO nexus_reader
            USING (workspace_id = (NULLIF(current_setting('app.workspace_id', true), ''))::uuid);
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexus_reader') THEN
        DROP POLICY IF EXISTS threads_reader_workspace ON threads;
        CREATE POLICY threads_reader_workspace ON threads
            FOR SELECT TO nexus_reader
            USING (workspace_id = (NULLIF(current_setting('app.workspace_id', true), ''))::uuid);
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexus_writer') THEN
        DROP POLICY IF EXISTS threads_writer_all ON threads;
        CREATE POLICY threads_writer_all ON threads
            FOR ALL
            TO nexus_writer
            USING (true)
            WITH CHECK (true);
    END IF;
END $$;

-- 6. Grant permissions on users, workspace_members, sales_clean
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexus_writer') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE users, workspace_members TO nexus_writer;
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'sales_clean') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.sales_clean TO nexus_writer;
        END IF;
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'user_data' AND table_name = 'ds_superstore') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON user_data.ds_superstore TO nexus_writer;
        END IF;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexus_reader') THEN
        GRANT SELECT ON TABLE users, workspace_members TO nexus_reader;
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'sales_clean') THEN
            GRANT SELECT ON public.sales_clean TO nexus_reader;
        END IF;
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'user_data' AND table_name = 'ds_superstore') THEN
            GRANT SELECT ON user_data.ds_superstore TO nexus_reader;
        END IF;
    END IF;
END $$;
