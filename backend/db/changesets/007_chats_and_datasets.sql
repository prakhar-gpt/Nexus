-- Changeset 007: First-class threads with workspace ownership, RLS, and per-chat dataset selection.
-- Purges ghost "Schema Analysis" runs and backfills real threads.

-- 1. Purge ghost runs created during schema analysis / upload proposals
DELETE FROM runs 
WHERE question = 'Schema Analysis' 
   OR answer LIKE '{"table_label"%' 
   OR answer LIKE '{"table_name"%';

-- 2. Create first-class threads table with (workspace_id, id) composite primary key
CREATE TABLE IF NOT EXISTS threads (
    id                   text NOT NULL,
    workspace_id         bigint NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    title                text NOT NULL DEFAULT 'New Conversation',
    selected_dataset_ids bigint[] NOT NULL DEFAULT '{}',
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, id)
);

CREATE INDEX IF NOT EXISTS idx_threads_workspace ON threads(workspace_id);

-- 3. RLS: strictly scoped by app.workspace_id for nexus_reader
ALTER TABLE threads ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS threads_reader_workspace ON threads;
CREATE POLICY threads_reader_workspace ON threads
    FOR SELECT TO nexus_reader
    USING (workspace_id = (NULLIF(current_setting('app.workspace_id', true), ''))::bigint);

DROP POLICY IF EXISTS threads_writer_all ON threads;
CREATE POLICY threads_writer_all ON threads
    FOR ALL
    TO nexus_writer
    USING (true)
    WITH CHECK (true);

GRANT SELECT ON threads TO nexus_reader;
GRANT ALL ON threads TO nexus_writer;

-- 4. Normalize any existing runs with NULL thread_id to 'default'
UPDATE runs 
SET checker_result = jsonb_set(
    coalesce(checker_result::jsonb, '{}'::jsonb), 
    '{thread_id}', 
    '"default"'::jsonb
)
WHERE (checker_result->>'thread_id') IS NULL;

-- 5. Backfill threads from valid existing runs, assigning all current workspace datasets by default
INSERT INTO threads (id, workspace_id, title, selected_dataset_ids, created_at, updated_at)
SELECT 
    coalesce(r.checker_result->>'thread_id', 'default') AS id,
    r.workspace_id,
    min(r.question) AS title,
    coalesce(
        (SELECT array_agg(d.id ORDER BY d.id) FROM datasets d WHERE d.workspace_id = r.workspace_id),
        '{}'
    ) AS selected_dataset_ids,
    min(r.created_at) AS created_at,
    max(r.created_at) AS updated_at
FROM runs r
WHERE (r.checker_result->>'deleted') IS NULL
GROUP BY r.workspace_id, coalesce(r.checker_result->>'thread_id', 'default')
ON CONFLICT (workspace_id, id) DO NOTHING;

