# Active Context

Week 2 is complete. Ingestion lives in `app/packages/ingest/`. `column_mapping` and `quarantine` exist on `nexus_db`. The six test files pass, and the Week 1 eval still passes.

A header at RapidFuzz 70 or above is auto-mapped. Below 70, `app/kb/column_hints.md` proposes the column and load waits for confirmation. No model is called. Ambiguous dates are day-month-year. Formula-like text is stored with a leading apostrophe.

The writer role password is only in `.env`.

Unresolved:

- Whether this server has pgvector.
- `documents` / `chunks` and `runs` still have no `workspace_id` in the v2 column list.
- The Superstore extract still cannot answer discount, quantity, cost, or profit questions.
- v2 open questions: hosted model and budget; public repo and demo or not; first role and add-on; auth in v1 or single-user local mode.
- GitHub Actions for the eval script is Week 4.

Next action: Week 3 when asked. The single dashboard, SSE streaming, the trace panel, and data health.
