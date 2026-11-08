The question path is documented in `context/agent/`. Start at `context/agent/README.md`. Each step has its own file detailing entry, model selection, thread state, model routing, tools execution, SQL execution, checker verification, streaming, and UI rendering.

The backend is fully modularized with strict separation of concerns across `app/packages/agent/` (`state.py`, `formatting.py`, `tools/`, `nodes/`, `graph.py`) and `app/apps/api/` (`schemas.py`, `sse.py`, `services/`, `routers/`, `main.py`).

The frontend is refactored into senior-grade modular components under `app/apps/web/components/sidebar/` (`WorkspaceSelector`, `ThreadList`, `IngestionSection`), `WorkspacesModal`, `ChatPane`, and `AnswerChart`. The UI runs on `http://localhost:3000` with Claude-style thread management, thread deletion, full data room browsing, and minimal Nexus branding. The FastAPI backend runs on `http://localhost:8000`.

A second `Superstore.csv` upload on workspace 1 is waiting for confirmation of `Sales` → `revenue`. Confirming it would load those rows again on top of the 9800 already stored.

Resolved in this turn:
- Frontend architecture decomposition: deleted monolithic `data-pane.tsx` and created isolated components under `components/sidebar/` (`WorkspaceSelector`, `ThreadList`, `IngestionSection`, `index.tsx`).
- Workspace Browser: added `WorkspacesModal` to view all data rooms with creation dates, file counts, and query metrics, with one-click switching and inline creation.
- Chat Deletion: added `DELETE /workspaces/{id}/threads/{thread_id}` endpoint and UI delete button with hover reveal and confirmation.
- Build verification: Next.js 16 production build compiles in ~3.2s with 0 errors.

Unresolved / Planned for Implementation:
- **Deterministic Python Math Tool (`run_python`)**: Sandboxed execution for compound growth and statistical metrics, registering outputs into `state` and expanding `checker.py` to trace Python results without caveats.
- **Dynamic Dataset Column Support (`attributes JSONB`)**: Update `sales_clean` with a JSONB column to preserve arbitrary client columns dynamically while retaining canonical anchors (`order_date`, `revenue`/`quantity`).
- **CI & Deployment (Week 4)**: GitHub Actions workflow for `app/eval/runner.py` regression checks on push, and Docker Compose packaging.
- **Knowledge Base / Document Q&A**: pgvector semantic retrieval over PDF diligence memos.
- The Superstore extract contains nulls for `quantity`, `unit_price`, `discount_pct`, `cost`, `profit`, and `channel`; the agent continues to refuse those queries while the deterministic checker acts as backstop.
