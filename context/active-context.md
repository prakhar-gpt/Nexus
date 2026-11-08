The question path is written down in `context/agent/`. Start at `context/agent/README.md`. Each step has its own file: entry, model, thread, the model's choice, the three tools, SQL, the checker, streaming, and the screen.

The screen is a chat. Assistant text is markdown while tokens arrive. Tokens keep their spaces. The answer is a sentence or a markdown list. The API on port 8000 is the process that loaded this prompt. Restart it after a prompt or `graph.py` change.

A second `Superstore.csv` upload on workspace 1 is waiting for confirmation of `Sales` → `revenue`. Confirming it would load those rows again on top of the 9800 already stored.

Unresolved:

- Whether this server has pgvector. Document questions are not built.
- `documents` / `chunks` still have no `workspace_id` in the v2 column list. `runs.workspace_id` was added (Decision 20).
- The Superstore extract still cannot answer discount, quantity, cost, or profit questions. The agent is told to refuse those; the checker is the backstop.
- v2 open questions: public repo and demo or not; first role and add-on; auth in v1 or single-user local mode. The hosted model is Groq for now (Decision 22).
- GitHub Actions for the eval script is Week 4.
- The in-memory thread does not survive an API restart. After a restart the model sees the stored questions and answers, not the earlier tool calls. Older stored answers may still be field dumps.

Next action: the user can ask in the chat. Week 4 remains the add-on, Docker, and CI.
