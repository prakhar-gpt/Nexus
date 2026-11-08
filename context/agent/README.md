# How a question is answered

Read this file, then the step files in order, the first time you touch the agent. After that, open only the step you are changing. Live code wins if a note disagrees. Update the note.

The loop workflow assembler lives in `backend/agent/graph.py`, with nodes implemented in `backend/agent/nodes.py` and modular tool definitions/handlers in `backend/agent/tools/`. This line runs when `graph.py` is imported:

```python
GRAPH = Agent(chat_model())
```

The prompt in `backend/agent/prompts/system.md` is also read at import. Restart the API after changing either one. The running process does not pick up a new prompt or a new graph by itself.

| Order | File | What that step owns |
|---|---|---|
| 1 | [01-entry.md](01-entry.md) | The chat route (`routers/workspaces.py`, `services/chat_service.py`) calls `stream()`, not `ask()` |
| 2 | [02-model.md](02-model.md) | Which hosted model is called, and how the key is read (`backend/agent/model.py`) |
| 3 | [03-thread.md](03-thread.md) | Workspace memory, and what is wiped at the start of a question |
| 4 | [04-choose.md](04-choose.md) | `nodes.py` (`agent_node`) calls the model; `tools/` exposes the 4 tool schemas |
| 5 | [05-tools.md](05-tools.md) | `nodes.py` (`tools_node`) executes `get_schema`, `run_sql`, `read_kb`, and `run_python` |
| 6 | [06-sql.md](06-sql.md) | The SELECT guard, the reader role, 25-row preview cap, and 200-row limit |
| 7 | [07-checker.md](07-checker.md) | Every number in the answer must trace to tool outputs or query context (`backend/agent/checker.py`) |
| 8 | [08-stream.md](08-stream.md) | Tool lines and tokens (`nodes.py` chunk extractors) stream live via SSE |
| 9 | [09-screen.md](09-screen.md) | The chat UI in `frontend/` paints those events, including markdown and audit bar |

Product shape, stack, and tables stay in `architecture.md`. Module rules stay in `agents.md`. This folder is the turn itself.

## The turn

```text
POST /workspaces/{id}/chat         backend/api/routers/workspaces.py -> services/chat_service.py
  stream()                         backend/agent/graph.py
    Agent.watch()                  graph.py
      prepare thread               03-thread.md
      agent_node                   04-choose.md (backend/agent/nodes.py)
        tools_node                 05-tools.md (backend/agent/nodes.py, backend/agent/tools/) -> back to agent
        checker_node               07-checker.md (backend/agent/nodes.py, backend/agent/checker.py) -> END
      yield step / token           08-stream.md (backend/agent/nodes.py chunk extractors)
  save runs, then check and done   01-entry.md (backend/api/services/chat_service.py)
  screen appends tokens            09-screen.md (frontend/)
```

`ask()` still exists for synchronous evaluation (`runner.py`) and unit tests. The chat UI uses `stream()` / `watch()` which yields while the graph runs.

## Facts that are easy to get wrong

- Separation of concerns: `backend/agent/` is structured as `state.py` (state definitions/limits), `nodes.py` (graph nodes and token extractors), `tools/` (`get_schema.py`, `run_sql.py`, `read_kb.py`, `run_python.py`), `graph.py` (workflow assembler), `checker.py` (verification), and `sandbox.py` (subprocess execution).
- `backend/api/` is structured with domain routers (`workspaces.py`, `uploads.py`, `runs.py`, `eval.py`) with colocated Pydantic models, and domain services (`chat_service.py`, `workspace_service.py`, `upload_service.py`, `eval_service.py`).
- The 4 active tools are: `get_schema`, `run_sql`, `read_kb`, and `run_python`. All 4 are registered in `backend/agent/tools/__init__.py`.
- `run_python` normalizes leading indentation and strips markdown code fences via `clean_code()` before AST parsing, avoiding `IndentationError` when LLMs output indented scripts.
- `rows`, `sqls`, `steps`, and `step_count` start empty on every question. Memory is the message list only. A follow-up must query again. An earlier answer is not a source of numbers.
- `MAX_TOOL_STEPS = 8` tool rounds per question. The counter resets when the next question starts.
- Groq tokens arrive with a leading space (`" revenue"`). `extract_visible_chunk` keeps it. `extract_text_delta` strips only the finished answer. Stripping each token glues the words and breaks markdown until a refresh loads the stored sentence.
- A chunk that carries `tool_call_chunks` is not shown. Blocks typed `reasoning`, `thinking`, or `reasoning_content` are not shown.
- The checker is not a line in the chat. The screen drops any step whose tool is `checker`.
- `MemorySaver` lives in the API process. After a restart the model sees the last eight stored questions and answers from Postgres `runs`.
- Workspace 1 `sales_clean` has 9800 rows, order dates 2015-01-03 through 2018-12-30, revenue sum 2261536.78. `quantity`, `unit_price`, `discount_pct`, `cost`, `profit`, and `channel` are null.
- Do not print `.env`. Do not copy a key into this folder.

## How to run it

```text
uvicorn main:app --reload --port 8000   # in backend/
npm run dev --port 3000                 # in frontend/
pytest backend/tests                    # run all 20 tests
python backend/eval/runner.py           # run 30-question golden set
```

One API process on port 8000. Do not start a second listener.
