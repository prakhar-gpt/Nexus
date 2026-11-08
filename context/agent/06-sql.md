# 6. Read-only SQL

`run_sql` in `app/packages/agent/run_sql.py` is what `_query` calls, imported into the graph as `execute_sql`. Two checks happen before Postgres sees the text.

## The parser

`guard_sql` in `app/packages/agent/sql_guard.py` raises `sql_guard.SqlRejected` when any of these fail:

- empty, or longer than 8000 characters
- a semicolon other than one trailing semicolon, which is stripped
- the statement is not `SELECT` or `WITH`
- a forbidden keyword, including `insert`, `update`, `delete`, `drop`, `set`, `into`, and the word `table`
- a forbidden function (`pg_read_file`, `pg_sleep`, `dblink`, `set_config`, and the others in `_DANGEROUS_FN`)
- a schema name (`public`, `pg_catalog`, `information_schema`, `pg_temp`)
- a `FROM` or `JOIN` target that is not `sales_clean` and not a CTE name defined in the statement
- no read of `sales_clean` at all

Comments are stripped before those checks. String literals are masked so a word inside quotes is not a keyword. `extract(...)`, `trim(...)`, `substring(...)`, and `overlay(...)` are masked so the word `from` inside them is not a table.

The word `table` is forbidden on purpose. The prompt tells the model not to use it. `FROM sales_clean` is the only allowed relation.

## The connection

The cleaned statement is wrapped and run as `nexus_reader` through `psql`:

```sql
BEGIN;
SET LOCAL app.workspace_id = '<id>';
SET LOCAL statement_timeout = '5000';
SET LOCAL transaction_read_only = on;
SELECT * FROM (
  <cleaned statement>
) AS agent_result
LIMIT 200;
COMMIT;
```

`app/packages/agent/db.py` shells to `C:\Program Files\PostgreSQL\18\bin\psql.exe` against `localhost:5432` / `nexus_db`. The password is `NEXUS_READER_PASSWORD` only. A failure becomes `run_sql.SqlRejected`. That class is not the same object as `sql_guard.SqlRejected`. Callers catch both.

Row-level security on `sales_clean` shows the reader only the workspace named by `app.workspace_id`. The policy is `app/infra/reader.sql`. The table owner is a superuser and bypasses that policy, which is why the agent must not connect as the owner.

The cap is 200 rows (`ROW_LIMIT`) even if the model's own SQL has no `LIMIT`. Timeout is 5 seconds (`TIMEOUT_MS`). Output is CSV parsed into a list of dicts of strings.

`populated_count` is a helper for the eval. It only accepts the names in `MEASURE_COLUMNS`. The graph does not call it. `get_schema` counts those columns itself.

Workspace 1 today: 9800 rows, revenue `2261536.78`, dates 2015-01-03 through 2018-12-30. Region sums that have already been checked: West 710219.68, East 669518.73, Central 492646.91, South 389151.46. `quantity`, `unit_price`, `discount_pct`, `cost`, `profit`, and `channel` are null. CSV `Sales` was mapped to `revenue`.
