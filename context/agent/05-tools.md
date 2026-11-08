# 5. The tools node

`_tools` in `graph.py` is the only place a tool runs. It walks `last.tool_calls`. The current model is asked to send one call at a time, and `gpt-oss` does not do parallel calls. `step_count` still increases by 1 for the whole visit, not once per call.

For each call the node:

1. Emits a custom stream event with `status: "running"` and a sentence from `_status_line`, before the work.
2. Runs the branch below. `workspace_id` comes from state.
3. Emits the same `id` again with `status` `ok` or `error`, `ms`, and, for SQL, `query` plus `row_count`.
4. Appends a step dict and a `ToolMessage`.

| Tool name | Function | What the model receives back |
|---|---|---|
| `get_schema` | `_schema` | One line of `column=count` from `SCHEMA_SQL`, or `rejected: ...` |
| `run_sql` | `_query` → [06-sql.md](06-sql.md) | A CSV of the rows, or `0 rows`, or `rejected: ...` |
| `read_kb` | `_kb` | Up to 6000 characters of one file under `app/kb`, or `rejected: ...` |
| anything else | — | `rejected: unknown tool` |

`_emit` calls `get_stream_writer()`. During `ask()` / `invoke()` there is no writer. The `except` swallows that so tests do not crash. During `watch()` the writer is the custom stream. See [08-stream.md](08-stream.md).

Sentences the screen shows:

| Tool | While it runs | When it finishes |
|---|---|---|
| `get_schema` | Looking at the columns… | Looked at the columns |
| `run_sql` | Running a query… | Ran a query |
| `read_kb` | Reading the notes… | Read the notes |
| rejected | — | That step was rejected |

`SCHEMA_SQL` counts non-null values for `order_date`, `customer_id`, `product_id`, `segment`, `region`, `category`, `sub_category`, `revenue`, `quantity`, `unit_price`, `discount_pct`, `cost`, `profit`, and `channel`. It does not return sample rows. On workspace 1 the measure counts other than `revenue` are 0. The prompt says to answer `Cannot answer.` with no number when the question needs one of those empty columns.

`_query` keeps three things: the CSV text for the model, the row dicts for the checker, and the SQL string for `runs.sql_list`. A rejection returns no rows and no SQL, so a blocked statement is not stored as a query that ran.

`_kb` resolves the path under `app/kb` and rejects `..`, a path outside that root, and a missing file. It does not search. The model must name the file (`column_hints.md`, `metrics.md`, a playbook). `search_docs` is not this tool and is not built.

The node returns the extended `rows`, `sqls`, `steps`, and `step_count`. The graph then goes back to the agent node.
