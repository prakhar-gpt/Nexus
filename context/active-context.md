The question path is documented in `context/agent/`. Start at `context/agent/README.md`. Each step has its own file detailing entry, model selection, thread state, model routing, tools execution, SQL execution, checker verification, streaming, and UI rendering.

The backend is fully modularized with strict separation of concerns across `app/packages/agent/` (`state.py`, `formatting.py`, `tools/`, `nodes/`, `graph.py`) and `app/apps/api/` (`schemas.py`, `sse.py`, `services/`, `routers/`, `main.py`).

The screen is an interactive chat running on `http://localhost:3000`. The FastAPI backend runs on `http://localhost:8000`.

A second `Superstore.csv` upload on workspace 1 is waiting for confirmation of `Sales` → `revenue`. Confirming it would load those rows again on top of the 9800 already stored.

Unresolved / Next Up:

- Document ingestion and pgvector semantic retrieval (Week 4 milestone).
- CI workflow and automated regression testing via GitHub Actions for `app/eval/runner.py`.
- The Superstore extract contains nulls for `quantity`, `unit_price`, `discount_pct`, `cost`, `profit`, and `channel`; the agent continues to refuse those queries while the deterministic checker acts as backstop.
- MemorySaver caches thread sessions in API process memory; after an API restart, history is restored from the last eight stored runs in PostgreSQL.
