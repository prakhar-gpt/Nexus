# 5. The tools node

`create_tools_node` in `backend/agent/nodes.py` is the only place a tool runs. It walks `last.tool_calls`. The current model is asked to send one call at a time, and `gpt-oss` does not do parallel calls. `step_count` increases by 1 for the whole visit, not once per call.

For each call the node:

1. Emits a custom stream event with `status: "running"` and a sentence from `format_status_running`, before the work.
2. Dispatches to `execute_tool(name, args, workspace_id, last_sql_result)` in `backend/agent/tools/__init__.py`. `workspace_id` comes from state.
3. Emits the same `id` again with `status` `ok` or `error`, `ms`, and, for SQL, `query` plus `row_count`.
4. Appends a step dict and a `ToolMessage`.

| Tool name | Module in `backend/agent/tools/` | What the model receives back |
|---|---|---|
| `get_schema` | `get_schema.py` | Column counts, dynamic JSONB attributes, and analytical capabilities |
| `run_sql` | `run_sql.py` → [06-sql.md](06-sql.md) | Formatted preview of rows (up to 25 rows), or `0 rows`, or `rejected: ...` |
| `read_kb` | `read_kb.py` | Up to 6000 characters of one file under `backend/kb`, or `rejected: ...` |
| `run_python` | `run_python.py` | Key-value numeric calculation results, stdout output, or `rejected: ...` |
| anything else | — | `rejected: unknown tool` |

`_emit` calls `get_stream_writer()`. During `ask()` / `invoke()` there is no writer. The `except` swallows that so tests do not crash. During `watch()` the writer is the custom stream. See [08-stream.md](08-stream.md).

Sentences the screen shows:

| Tool | While it runs | When it finishes |
|---|---|---|
| `get_schema` | Looking at the columns… | Looked at the columns |
| `run_sql` | Running a query… | Ran a query |
| `read_kb` | Reading the notes… | Read the notes |
| `run_python` | Calculating… | Calculated |
| rejected | — | That step was rejected |

`get_schema` counts non-null values for canonical columns, reports dynamic `attributes` JSONB keys with sample values and cast expressions, and lists analytical capabilities (e.g. `margin`, `discount`, `trend`). On workspace 1 the measure counts other than `revenue` are 0. The prompt says to answer `Cannot answer.` with no number when the question needs one of those empty columns.

`run_sql` keeps three things: preview text for the model (25 rows), all row dicts (up to 200) for the checker and Python dataframes, and the SQL string for `runs.sql_list`. A rejection returns no rows and no SQL, so a blocked statement is not stored as a query that ran.

`run_python` passes prior SQL rows as a pandas DataFrame `data`. Code is pre-processed with `clean_code()` to unindent leading whitespace and strip code fences, syntax-validated with AST, and executed in an isolated OS subprocess (no network, 10s timeout, 256MB cap). Extracted values are passed to `checker.py` as verified figures.

`read_kb` resolves the path under `backend/kb` and rejects `..`, a path outside that root, and a missing file. It does not search. The model must name the file (`column_hints.md`, `metrics.md`, a playbook). `search_docs` is not this tool and is not built.

The node returns the extended `rows`, `sqls`, `steps`, `python_results`, and `step_count`. The graph then goes back to the agent node.
