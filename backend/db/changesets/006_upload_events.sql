-- 006_upload_events.sql: Persistent upload events for zero-event-loss SSE replay
-- Safe to re-run: uses IF NOT EXISTS guards.

CREATE TABLE IF NOT EXISTS upload_events (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    upload_id  bigint NOT NULL REFERENCES uploads (id) ON DELETE CASCADE,
    seq        integer NOT NULL,
    stage      text NOT NULL,
    event_type text NOT NULL,
    label      text NOT NULL,
    payload    jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (upload_id, seq)
);

CREATE INDEX IF NOT EXISTS upload_events_upload_id_seq_idx ON upload_events (upload_id, seq);
CREATE INDEX IF NOT EXISTS upload_events_created_at_idx ON upload_events (created_at);

-- Grant appropriate permissions
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexus_writer') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE upload_events TO nexus_writer;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nexus_writer;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexus_ingest') THEN
        GRANT SELECT, INSERT, UPDATE ON TABLE upload_events TO nexus_ingest;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nexus_ingest;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexus_reader') THEN
        GRANT SELECT ON TABLE upload_events TO nexus_reader;
    END IF;
END
$$;

