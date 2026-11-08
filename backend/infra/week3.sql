-- Week 3. runs, feedback, and eval_results.
-- runs.workspace_id is not in the v2 column list. The chat route is per room,
-- so a run is stored with the room it answered. Decision 20.

CREATE TABLE IF NOT EXISTS runs (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    workspace_id bigint NOT NULL REFERENCES workspaces (id),
    question text NOT NULL,
    plan text,
    sql_list text,
    answer text,
    checker_result jsonb,
    latency_ms integer,
    tokens integer,
    cost numeric,
    model text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS runs_workspace_id_idx ON runs (workspace_id);

CREATE TABLE IF NOT EXISTS feedback (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id bigint NOT NULL REFERENCES runs (id),
    rating text NOT NULL,
    reason text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS eval_results (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    eval_run_id text NOT NULL,
    question_id text NOT NULL,
    passed boolean NOT NULL,
    metrics_json jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

GRANT SELECT, INSERT, UPDATE ON runs, feedback, eval_results TO nexus_writer;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nexus_writer;
