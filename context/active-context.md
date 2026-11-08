# Active Context

Week 1 is in progress. The user created empty database `nexus_db` on local PostgreSQL 18. `app/infra/schema.sql` and `app/infra/load_superstore.py` are not applied. A connection to `nexus_db` as `postgres` still fails with no password supplied. Do not store the password in the repo.

Unresolved after the load:

- Whether this server has pgvector. Not required for `sales_clean`.
- `documents` / `chunks` and `runs` still have no `workspace_id` in the v2 column list.
- This Superstore extract cannot answer discount, quantity, cost, or profit questions. Those `sales_clean` columns will be null.
- v2 open questions: hosted model and budget; public repo and demo or not; first role and add-on; auth in v1 or single-user local mode.

Next action: apply the schema and loader once a password is available, then verify `sales_clean` has 9800 rows.
