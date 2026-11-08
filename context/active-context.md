The question path is documented in `context/agent/`. Start at `context/agent/README.md`. Each step has its own file detailing entry, model selection, thread state, model routing, tools execution, SQL execution, checker verification, streaming, and UI rendering.

The backend is fully modularized with strict separation of concerns across `app/packages/agent/` (`state.py`, `formatting.py`, `tools/`, `nodes/`, `graph.py`) and `app/apps/api/` (`schemas.py`, `sse.py`, `services/`, `routers/`, `main.py`).

The frontend features a clean two-level navigation model:
1. **Data Rooms Hub (`WorkspacesView`)**: A clean landing page displaying all data rooms with file & query metrics, quick creation, and deletion.
2. **Focused Chat Interface**: When entering a data room, the user enters a clean conversation environment. The left sidebar is strictly focused on:
   - "← Data Rooms" navigation button to return to the hub.
   - Active data room card with a "Dataset" button to open the spreadsheet ingestion modal on demand.
   - Clean, lightweight thread list (+ New Chat, thread switching, thread deletion).
   - User profile with instant working Log Out.
3. Developer evaluation metrics (`SQL: 100%`, `Numbers: 100%`, `Refusals: 100%`) were removed from the user interface and remain an offline CI harness under `app/eval/runner.py`.

The UI runs on `http://localhost:3000` and the FastAPI backend runs on `http://localhost:8000`.

A second `Superstore.csv` upload on workspace 1 is waiting for confirmation of `Sales` → `revenue`. Confirming it would load those rows again on top of the 9800 already stored.

Unresolved / Planned for Implementation:
- **Deterministic Python Math Tool (`run_python`)**: Sandboxed execution for compound growth and statistical metrics, registering outputs into `state` and expanding `checker.py` to trace Python results without caveats.
- **Dynamic Dataset Column Support (`attributes JSONB`)**: Update `sales_clean` with a JSONB column to preserve arbitrary client columns dynamically while retaining canonical anchors (`order_date`, `revenue`/`quantity`).
- **CI & Deployment (Week 4)**: GitHub Actions workflow for `app/eval/runner.py` regression checks on push, and Docker Compose packaging.
- **Knowledge Base / Document Q&A**: pgvector semantic retrieval over PDF diligence memos.
- The Superstore extract contains nulls for `quantity`, `unit_price`, `discount_pct`, `cost`, `profit`, and `channel`; the agent continues to refuse those queries while the deterministic checker acts as backstop.
