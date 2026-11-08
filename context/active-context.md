The question path is documented in `context/agent/`. Start at `context/agent/README.md`. Each step has its own file detailing entry, model selection, thread state, model routing, tools execution, SQL execution, checker verification, streaming, and UI rendering.

The backend is fully modularized with strict separation of concerns across `app/packages/agent/` (`state.py`, `formatting.py`, `tools/`, `nodes/`, `graph.py`) and `app/apps/api/` (`schemas.py`, `sse.py`, `services/`, `routers/`, `main.py`).

The UI is running on `http://localhost:3000` with clean Claude-style multi-thread chat management, workspace switching/creation, and Nexus branding. The FastAPI backend runs on `http://localhost:8000`.

A second `Superstore.csv` upload on workspace 1 is waiting for confirmation of `Sales` → `revenue`. Confirming it would load those rows again on top of the 9800 already stored.

Resolved in this turn:
- Added multi-thread conversation support per workspace: a data room holds clean data and uploads, and analysts can create multiple independent chat threads inside it.
- Added Claude-style sidebar navigation: Data Room switcher with quick "+ New" room creation, thread list with active highlights and turn count badges, "+ New Chat" button, data source dropzone, and evaluation scorecard.
- Added minimal, clean "Nexus Copilot" branding to the desktop sidebar and mobile header.
- Added `/workspaces/{id}/threads` and `/workspaces/{id}/threads/{thread_id}/turns` endpoints.
- Updated LangGraph checkpointer key to `ws-{id}-thread-{thread_id}` for clean conversation isolation.

Unresolved / Planned for Implementation:
- **Deterministic Python Math Tool (`run_python`)**: Sandboxed execution for compound growth and statistical metrics, registering outputs into `state` and expanding `checker.py` to trace Python results without caveats.
- **Dynamic Dataset Column Support (`attributes JSONB`)**: Update `sales_clean` with a JSONB column to preserve arbitrary client columns dynamically while retaining canonical anchors (`order_date`, `revenue`/`quantity`).
- **CI & Deployment (Week 4)**: GitHub Actions workflow for `app/eval/runner.py` regression checks on push, and Docker Compose packaging.
- **Knowledge Base / Document Q&A**: pgvector semantic retrieval over PDF diligence memos.
- The Superstore extract contains nulls for `quantity`, `unit_price`, `discount_pct`, `cost`, `profit`, and `channel`; the agent continues to refuse those queries while the deterministic checker acts as backstop.
