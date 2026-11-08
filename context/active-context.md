# Active Context

Week 1 is complete on local PostgreSQL 18, database `nexus_db`.

`sales_clean` has 9800 Superstore rows. `run_sql` reads them as `nexus_reader` with workspace row-level security. The checker and `app/eval/runner.py` pass the 25-question golden set at 100% (targets 85% SQL correctness, 98% numeric faithfulness, 90% refusal accuracy). Five of the questions are refusals because quantity, unit price, discount, cost, profit, and channel are null.

Do not store the database password in the repo. The reader password is only in `.env`.

Unresolved:

- Whether this server has pgvector. Not required for `sales_clean`.
- `documents` / `chunks` and `runs` still have no `workspace_id` in the v2 column list.
- This Superstore extract cannot answer discount, quantity, cost, or profit questions.
- v2 open questions: hosted model and budget; public repo and demo or not; first role and add-on; auth in v1 or single-user local mode.
- GitHub Actions for the eval script is Week 4, not built.

Next action: Week 2 ingestion when asked. Parsing, header detection, RapidFuzz mapping, quarantine, and the six test files.
