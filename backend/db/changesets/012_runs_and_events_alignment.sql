-- Changeset 012: Add upload_id and agent_kind to runs, and ensure agent_events table exists.
-- Fixes missing column error: column runs.upload_id does not exist.

-- 1. Align runs table with SQLAlchemy ORM model
ALTER TABLE runs ADD COLUMN IF NOT EXISTS upload_id uuid REFERENCES uploads(id) ON DELETE CASCADE;
ALTER TABLE runs ADD COLUMN IF NOT EXISTS agent_kind text NOT NULL DEFAULT 'nexus';

CREATE INDEX IF NOT EXISTS idx_runs_upload_id ON runs(upload_id);
CREATE INDEX IF NOT EXISTS idx_runs_agent_kind ON runs(agent_kind);

-- 2. Align agent_events / upload_events table
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'upload_events') 
       AND NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'agent_events') THEN
        ALTER TABLE upload_events RENAME TO agent_events;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS agent_events (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid REFERENCES workspaces(id) ON DELETE CASCADE,
    run_id       uuid REFERENCES runs(id) ON DELETE CASCADE,
    upload_id    uuid REFERENCES uploads(id) ON DELETE CASCADE,
    agent_kind   text NOT NULL DEFAULT 'nexus',
    seq          integer NOT NULL,
    stage        text NOT NULL,
    event_type   text NOT NULL,
    label        text NOT NULL,
    payload      jsonb NOT NULL DEFAULT '{}',
    created_at   timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE agent_events ADD COLUMN IF NOT EXISTS workspace_id uuid REFERENCES workspaces(id) ON DELETE CASCADE;
ALTER TABLE agent_events ADD COLUMN IF NOT EXISTS run_id uuid REFERENCES runs(id) ON DELETE CASCADE;
ALTER TABLE agent_events ADD COLUMN IF NOT EXISTS agent_kind text NOT NULL DEFAULT 'nexus';

CREATE INDEX IF NOT EXISTS idx_agent_events_upload_seq ON agent_events(upload_id, seq);
CREATE INDEX IF NOT EXISTS idx_agent_events_run_id ON agent_events(run_id);

-- 3. Permissions
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexus_writer') THEN
        GRANT ALL ON TABLE agent_events TO nexus_writer;
        GRANT ALL ON TABLE runs TO nexus_writer;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexus_reader') THEN
        GRANT SELECT ON TABLE agent_events TO nexus_reader;
        GRANT SELECT ON TABLE runs TO nexus_reader;
    END IF;
END $$;
