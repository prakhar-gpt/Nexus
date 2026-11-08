# How a question is answered

Read this file, then the step files in order, the first time you touch the agent. After that, open only the step you are changing. Live code wins if a note disagrees. Update the note.

The loop workflow assembler lives in `app/packages/agent/graph.py`, with nodes decomposed into `app/packages/agent/nodes/` and tool handlers in `app/packages/agent/tools/`. This line runs when `graph.py` is imported:

```python
GRAPH = Agent(chat_model())
```

The prompt in `app/packages/agent/prompts/system.md` is also read at import. Restart the API after changing either one. The running process does not pick up a new prompt or a new graph by itself.

| Order | File | What that step owns |
|---|---|---|
| 1 | [01-entry.md](01-entry.md) | The chat route (`routers/workspaces.py`, `services/chat_service.py`) calls `stream()`, not `ask()` |
| 2 | [02-model.md](02-model.md) | Which hosted model is called, and how the key is read |
| 3 | [03-thread.md](03-thread.md) | Workspace memory, and what is wiped at the start of a question |
| 4 | [04-choose.md](04-choose.md) | `nodes/agent_node.py` calls the model; `tools/definitions.py` exposes tool schemas |
| 5 | [05-tools.md](05-tools.md) | `nodes/tools_node.py` and `tools/handlers.py` actually execute `get_schema`, `run_sql`, and `read_kb` |
| 6 | [06-sql.md](06-sql.md) | The SELECT guard, the reader role, and the row cap |
| 7 | [07-checker.md](07-checker.md) | Every number in the answer must be in this turn's rows or query context (`nodes/checker_node.py`) |
| 8 | [08-stream.md](08-stream.md) | Tool lines and tokens (`formatting.py`) leave the process as they happen |
| 9 | [09-screen.md](09-screen.md) | The chat paints those events, including markdown |

Product shape, stack, and tables stay in `architecture.md`. Module rules stay in `agents.md`. This folder is the turn itself.

## The turn

```text
POST /workspaces/{id}/chat         routers/workspaces.py -> services/chat_service.py
  stream()                         packages/agent/graph.py (aliased in loop.py)
    Agent.watch()                  graph.py
      prepare thread               03-thread.md
      agent node                   04-choose.md (nodes/agent_node.py)
        tools node                 05-tools.md (nodes/tools_node.py, tools/handlers.py) -> back to agent
        checker node               07-checker.md (nodes/checker_node.py) -> END
      yield step / token           08-stream.md (formatting.py)
  save runs, then check and done   01-entry.md (services/chat_service.py)
  screen appends tokens            09-screen.md
```

`ask()` still exists. Tests and the eval call it. The screen does not. `ask()` waits for the whole graph. `watch()` yields while the graph runs.

## Facts that are easy to get wrong

- The `@tool` functions in `tools/definitions.py` are empty. They exist so the model can see a schema. `nodes/tools_node.py` and `tools/handlers.py` run the real code. The model cannot pass `workspace_id`. That id is server state.
- Separation of concerns: `app/packages/agent/` is structured as `state.py` (state definitions/limits), `formatting.py` (token extraction/cleaning), `tools/` (`definitions.py`, `handlers.py`), `nodes/` (`agent_node.py`, `tools_node.py`, `checker_node.py`, `router.py`), and `graph.py` (workflow assembler).
- `app/apps/api/` is structured as `schemas.py` (Pydantic models), `sse.py` (event formatting), `services/` (`chat_service.py`, `workspace_service.py`, `upload_service.py`, `eval_service.py`), `routers/` (`workspaces.py`, `uploads.py`, `runs.py`, `eval.py`), and `main.py` (FastAPI app setup).
- There are two `SqlRejected` classes, one in `sql_guard.py` and one in `run_sql.py`. The tools node catches both.
- The tool is named `run_sql`. The imported function is `execute_sql`. Giving them the same name makes the tool object get called as if it were the function.
- `rows`, `sqls`, `steps`, and `step_count` start empty on every question. Memory is the message list only. A follow-up must query again. An earlier answer is not a source of numbers.
- Six tool rounds per question. The counter resets when the next question starts.
- Groq tokens arrive with a leading space (`" revenue"`). `_visible` keeps it. `_text` strips only the finished answer. Stripping each token glues the words and breaks markdown until a refresh loads the stored sentence.
- A chunk that carries `tool_call_chunks` is not shown. Blocks typed `reasoning`, `thinking`, or `reasoning_content` are not shown. `openai/gpt-oss-120b` spends most of its output tokens on reasoning, then emits the answer in a short burst.
- The checker is not a line in the chat. The screen drops any step whose tool is `checker`.
- `search_docs`, `run_python`, and `web_search` are named in `architecture.md` and are not wired.
- `MemorySaver` lives in the API process. After a restart the model sees the last eight stored questions and answers, not the earlier tool calls.
- Workspace 1 `sales_clean` has 9800 rows, order dates 2015-01-03 through 2018-12-30, revenue sum 2261536.78. `quantity`, `unit_price`, `discount_pct`, `cost`, `profit`, and `channel` are null. A second `Superstore.csv` upload is waiting on `Sales` → `revenue`. Confirming it would insert those rows again on top of the 9800.
- Do not print `.env`. Do not copy a key into this folder.

## How to run it

```text
python -m uvicorn apps.api.main:app --app-dir app --port 8000
npm run dev --port 3000          # in app/apps/web
python app/packages/agent/test_loop.py
python app/apps/api/test_api.py  # stubs stream(); does not call Groq
python app/eval/runner.py
```

One API process on port 8000. Do not start a second listener.
