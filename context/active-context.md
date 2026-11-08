The dashboard shell is in `app/apps/web` and is one route. It uses shadcn/ui preset `base-nova`. The three panes render empty and waiting states. A file stays in the browser. A question shows a "Not connected" card and does not call SQL. Run it with `npm run dev` in that folder.

Week 2 ingestion and the Week 1 eval are unchanged.

Unresolved:

- The FastAPI routes, SSE, and the chat loop are not built.
- LangGraph and a hosted model wait on a provider and a key.
- Whether this server has pgvector.
- `documents` / `chunks` and `runs` still have no `workspace_id` in the v2 column list.
- The Superstore extract still cannot answer discount, quantity, cost, or profit questions.
- v2 open questions: hosted model and budget; public repo and demo or not; first role and add-on; auth in v1 or single-user local mode.
- GitHub Actions for the eval script is Week 4.

Next action: the API, when asked.
