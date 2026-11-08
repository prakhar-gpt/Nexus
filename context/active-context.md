# Active Context

Week 1 schema and Superstore load are applied on local PostgreSQL 18, database `nexus_db`.

`workspaces` has one row, `Superstore`. `uploads` has one row for `Superstore.csv`. `sales_clean` has 9800 rows. Order dates run from 2015-01-03 to 2018-12-30. Revenue sums to 2261536.78. Quantity, unit price, discount, cost, profit, and channel are null.

Do not store the database password in the repo.

Unresolved:

- Week 1 still needs the read-only `run_sql` tool, the 25-question golden set, the number checker, and the CI eval script.
- Whether this server has pgvector. Not required for `sales_clean`.
- `documents` / `chunks` and `runs` still have no `workspace_id` in the v2 column list.
- This Superstore extract cannot answer discount, quantity, cost, or profit questions.
- v2 open questions: hosted model and budget; public repo and demo or not; first role and add-on; auth in v1 or single-user local mode.

Next action: build the read-only `run_sql` tool against `sales_clean`.
