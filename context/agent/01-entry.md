# 1. The chat route

A question enters at `POST /workspaces/{id}/chat` routed via `app/apps/api/routers/workspaces.py` and handled by `app/apps/api/services/chat_service.py`. The handler verifies the workspace exists, validates the request via `ChatRequest` in `app/apps/api/schemas.py`, strips the question, and refuses an empty query.

The screen uses `stream()` from `app/packages/agent/graph.py` (aliased in `app/packages/agent/loop.py`):

```python
from packages.agent.graph import ask, stream

def stream(question, workspace_id, **kwargs):
    agent = kwargs.pop("agent", None) or GRAPH
    yield from agent.watch(question, workspace_id, **kwargs)
```

`GRAPH` is the process-wide agent built at import. Tests pass `agent=` so they do not call Groq. `app/apps/api/test_api.py` replaces `api.stream` with a fake iterator. If that stub is pointed at `ask` again, the test calls the hosted model.

`chat()` in `chat_service.py` walks that iterator and formats server-sent events using `app/apps/api/sse.py` as each item arrives. It does not wait for the graph and then dump every event.

| Yield from `watch()` | SSE the route writes |
|---|---|
| `("step", {id, tool, status, detail, ms, query?})` | `event: step`, and `event: sql` when `query` is set |
| `("token", text)` | `event: token` with `{"text": text}` |
| `("result", dict)` | held, not sent yet |

After the iterator finishes, the service saves the run in `runs` (`chat_service.save_run_record`) and then sends:

- `sql` again, with the joined queries and `len(rows)`, when any SQL ran
- `check` with `kind`, `verified`, and `untraced`
- `done` with `run_id`, `latency_ms`, `cost` 0, `tokens` 0, `model`, `rows`, and `answer`

`done.answer` is the sentence the checker stored. The screen replaces the streamed text with it so the live bubble matches a refresh. See [09-screen.md](09-screen.md).

`tokens` and `cost` on the row are always 0. The model name stored is `nexus_name` from [02-model.md](02-model.md), for example `groq/openai/gpt-oss-120b`.

The response is `StreamingResponse` with `Cache-Control: no-cache` and `X-Accel-Buffering: no`. CORS allows `http://localhost:3000` and `http://127.0.0.1:3000` only.

`ask()` is the same graph with `invoke` instead of `stream`. The eval and `test_loop.py` use it. The screen must not.

Upload progress is a different stream: `GET /uploads/{id}/events` via `EventSource` handled in `app/apps/api/routers/uploads.py`. Chat is `POST`, so the screen uses `fetch` and `readSse` in `app/apps/web/lib/api.ts`, not `EventSource`.
