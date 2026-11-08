# Architecture
This project is a single-dashboard Retail Data Room Copilot with a focus on deterministic numeric accuracy and data observability.

## Tech Stack
* **Frontend:** Next.js (TypeScript, Tailwind, shadcn/ui, Recharts). Single 3-pane dashboard (Left: Data/Health, Center: Chat, Right: Trace/Eval). No multi-page routing.
* **Backend:** FastAPI (Python, Pydantic, Background Tasks for ingestion).
* **Agent:** LangGraph (Single loop with tools: `run_sql`, `run_python`, `search_docs`). 
* **Database:** PostgreSQL with `pgvector`.
* **Mapping:** RapidFuzz heuristic matching first, LLM fallback only if < 70% confidence.

## Core Rules
* **No LLM Math:** The agent never calculates numbers itself. All math is executed via the `run_sql` tool against clean Postgres tables.
* **Independent Checker:** A deterministic Python script intercepts the agent's drafted answer and mathematically verifies every number against the SQL output before rendering.

## Data model
Section 6 of the v2 product document lists 9 Postgres tables. `workspaces` is the Data Room. `uploads.workspace_id` hangs files off a room. `column_mapping`, `sales_clean`, and `quarantine` hang off `uploads.id`; `sales_clean` also stores `workspace_id` so questions can be scoped without joining. `documents` / `chunks` is the pgvector store (`chunk_id` under `doc_id`). `feedback.run_id` points at `runs`. `eval_results` is keyed by `eval_run_id` and `question_id`. The listed columns do not link `runs`, `documents` / `chunks`, or `eval_results` to a workspace. Neo4j is an add-on, not part of this schema. The knowledge base is markdown, not tables.