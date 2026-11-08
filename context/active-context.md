# Active Context

The v2 product document is incorporated. No application code and no DDL exist yet. Week 1 has not started.

Unresolved before the schema is created:

- Which existing Postgres database to use, and whether that server already has pgvector.
- `documents` / `chunks` and `runs` have no `workspace_id` in the v2 column list, but retrieval and queries must be workspace-scoped.
- `datasets/Superstore/Superstore.csv` has sales and identifiers only. It has no quantity, unit price, discount, cost, or profit. Cost and profit are optional; margin and discount questions cannot be answered from this file until those columns exist.
- v2 open questions: hosted model and monthly budget; whether the repo and demo video are public; which role is first and therefore which one or two add-ons; authentication in v1 or single-user local mode.

Next action, when asked: Week 1 on the existing Postgres. Create the schema, then load Superstore into `sales_clean`. Do not add a Docker database.
