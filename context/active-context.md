The dashboard in `app/apps/web` calls the FastAPI app in `app/apps/api`. One route, three panes. Chat streams schema, SQL, the checker, and the answer for a golden-set question. Other questions are refused when the column is empty, or left unanswered. No model is called. The document chip stays inactive.

Run the API with `python -m uvicorn apps.api.main:app --app-dir app --port 8000` and the screen with `npm run dev` in `app/apps/web`.

A second `Superstore.csv` upload on workspace 1 is waiting for confirmation of `Sales` → `revenue`. Confirming it would load those rows again on top of the 9800 already stored.

Unresolved:

- LangGraph and a hosted model wait on a provider choice. Keys may exist in `.env`; none are used.
- Whether this server has pgvector. Document questions are not built.
- `documents` / `chunks` still have no `workspace_id` in the v2 column list. `runs.workspace_id` was added (Decision 20).
- The Superstore extract still cannot answer discount, quantity, cost, or profit questions.
- v2 open questions: hosted model and budget; public repo and demo or not; first role and add-on; auth in v1 or single-user local mode.
- GitHub Actions for the eval script is Week 4.

Next action: a model for the planner, when a provider is chosen. Week 4 remains the add-on, Docker, and CI.
