# Active Context

Week 1 database setup is paused before any DDL. Use the existing local PostgreSQL and pgAdmin; do not add Docker Postgres. The v2 spec's nine tables are recorded in `architecture.md` and have not been created. Unresolved: whether to create all nine now or only `sales_clean` for the Superstore load, and which existing database to use. `datasets/Superstore/Superstore.csv` has Sales and identifiers, and does not include quantity, discount, profit, cost, or unit price.
