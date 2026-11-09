-- Changeset 010: High-performance expression and foreign key indexes for room/chat load
-- Accelerates list_threads, get_turns, and dataset lookups

CREATE INDEX IF NOT EXISTS idx_runs_ws_thread ON runs(workspace_id, ((checker_result->>'thread_id')));
CREATE INDEX IF NOT EXISTS idx_runs_ws_created ON runs(workspace_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_datasets_workspace ON datasets(workspace_id);
CREATE INDEX IF NOT EXISTS idx_quarantine_upload ON quarantine(upload_id);
CREATE INDEX IF NOT EXISTS idx_uploads_ws_created ON uploads(workspace_id, created_at DESC);
