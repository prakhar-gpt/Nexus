# 1. The chat route

A question enters at `POST /workspaces/{id}/chat` routed via `backend/api/routers/workspaces.py` and handled by `backend/api/services/chat_service.py`. The handler verifies the workspace exists, validates the request via `ChatRequest` (colocated in `routers/workspaces.py`), strips the question, and refuses an empty query.

The screen uses `stream()` from `backend/agent/graph.py`:

```python
from agent.graph import ask, stream

def stream(question, workspace_id, **kwargs):
    agent = kwargs.pop("agent", None) or GRAPH
    yield from agent.watch(question, workspace_id, **kwargs)
```

`GRAPH` is the process-wide agent built at import. Tests pass `agent=` so they do not call Groq. `backend/tests/test_api.py` replaces `api.stream` with a fake iterator.

`chat()` in `chat_service.py` walks that iterator and formats server-sent events using `format_sse()` as each item arrives. It does not wait for the graph and then dump every event.

| Yield from `watch()` | SSE the route writes |
|---|---|
| `("step", {id, tool, status, detail, ms, query?})` | `event: step`, and `event: sql` when `query` is set |
| `("token", text)` | `event: token` with `{"text": text}` |
| `("result", dict)` | held, not sent yet |

After the iterator finishes, the service saves the full audit run in `runs` (`chat_service.save_run`), preserving `steps`, `tools_used`, and `python_results`, and then sends:

- `sql` again, with the joined queries and `len(rows)`, when any SQL ran
- `check` with `kind`, `verified`, and `untraced`
- `done` with `run_id`, `latency_ms`, `cost` 0, `tokens` 0, `model`, `rows`, and `answer`

`done.answer` is the sentence the checker stored. The screen replaces the streamed text with it so the live view matches a refresh. See [09-screen.md](09-screen.md).

`tokens` and `cost` on the row are 0 unless provider token counts are returned. The model name stored is `nexus_name` from [02-model.md](02-model.md), for example `groq/openai/gpt-oss-120b`.

The response is `StreamingResponse` with `Cache-Control: no-cache` and `X-Accel-Buffering: no`. CORS allows `http://localhost:3000` and `http://127.0.0.1:3000`.

`ask()` is the same graph with `invoke` instead of `stream`. The eval and unit tests use it. The screen must not.

Upload progress is a different stream: `GET /uploads/{id}/events` via `EventSource` handled in `backend/api/routers/uploads.py`. Chat is `POST`, so the screen uses `fetch` and `readSse` in `frontend/lib/api.ts`, not `EventSource`.
