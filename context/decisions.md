# Architectural Decisions (ADRs)

* **Decision 1:** Use RapidFuzz for column mapping instead of an LLM.
  * *Reason:* Sub-millisecond latency, zero cost, and highly deterministic for standard retail headers. LLMs are reserved strictly for fallback on ambiguous columns.
* **Decision 2:** Single LangGraph loop instead of a multi-agent system.
  * *Reason:* Reduces latency and compounding error rates. Complexity must be justified by measured eval failures.
* **Decision 3:** Ingestion runs via FastAPI Background Tasks.
  * *Reason:* Eliminates the need for Celery/Redis infrastructure in the MVP.
* **Decision 4:** Audit via Python Checker, not an Audit Agent.
  * *Reason:* LLMs hallucinating verifications of other LLMs is unreliable. Regex + SQL JSON cross-referencing guarantees mathematical fidelity.
* **Decision 5 (2026-11-08):** Week 1 uses the existing local PostgreSQL and pgAdmin. Do not add a Docker Postgres service.
  * *Reason:* Postgres and pgAdmin are already installed.
  * *Rejected:* `pgvector/pgvector:pg15` via `app/infra/docker-compose.yml`.
  * *Files affected:* none yet. No DDL has been applied.

Decisions 6–13 were incorporated from the v2 product document on 2026-11-08. The resulting design is in `architecture.md`.

* **Decision 6 (2026-11-08):** Clean Postgres tables are the source of truth at question time. Keep the raw file for lineage and debugging.
  * *Rejected:* Re-reading the upload to answer a question.
* **Decision 7 (2026-11-08):** pgvector runs in the same Postgres as the tables.
  * *Rejected:* A separate vector database. Azure AI Search remains a later swap.
* **Decision 8 (2026-11-08):** The knowledge base is markdown in the repo.
  * *Rejected for v1:* Neo4j. It is an add-on only.
* **Decision 9 (2026-11-08):** v1 retrieval is pgvector semantic search plus a metadata filter.
  * *Rejected for v1:* Hybrid BM25 and a cross-encoder reranker.
* **Decision 10 (2026-11-08):** Web search is off by default. A run that uses it must be labelled external.
* **Decision 11 (2026-11-08):** Streams use server-sent events.
* **Decision 12 (2026-11-08):** The UI is one dashboard with three panes.
  * *Rejected:* A nine-screen app and multi-page routing.
* **Decision 13 (2026-11-08):** v1 accepts one canonical sales shape plus optional documents.
  * *Rejected:* Chat with any file. Payroll, wide pivots, and free-form reports are out of scope.
* **Decision 14 (2026-11-08):** The Week 1 database on the existing PostgreSQL 18 server is named `nexus_db`.
  * *Reason:* The user named it.
  * *Files affected:* `app/infra/schema.sql`, `app/infra/load_superstore.py`.
* **Decision 15 (2026-11-08):** The first DDL creates `workspaces`, `uploads`, and `sales_clean` only. `sales_clean` has a surrogate `id`. Quantity, unit price, discount, cost, profit, and channel are nullable.
  * *Reason:* `sales_clean` foreign keys need the two parent tables. Business columns do not uniquely identify a line. The checked-in Superstore extract has revenue and no quantity, discount, cost, profit, unit price, or channel.
  * *Rejected:* Creating all nine tables before any of them are used. Loading this file into NOT NULL measure columns.
  * *Files affected:* `app/infra/schema.sql`, `app/infra/load_superstore.py`.
* **Decision 16 (2026-11-08):** `run_sql` uses the `nexus_reader` role, row-level security on `workspace_id`, a SELECT-only parser, a read-only transaction, a 5 second timeout, and a 200 row cap.
  * *Reason:* Agent SQL must not run as the table owner. The owner is a superuser and bypasses row-level security.
  * *Rejected:* Executing agent SQL as `postgres`.
  * *Files affected:* `app/packages/agent/`, `app/infra/reader.sql`, `app/eval/`.
* **Decision 17 (2026-11-08):** Week 2 adds `column_mapping` and `quarantine`. `sales_clean` allows a customer id or a product id, and revenue or quantity. Segment, region, category, and sub-category may be empty.
  * *Reason:* Domain fit requires one identifier and one measure, not every canonical column. The Week 1 file happened to contain the extra columns.
  * *Files affected:* `app/infra/ingest_tables.sql`, `app/infra/schema.sql`.
* **Decision 18 (2026-11-08):** Headers below a RapidFuzz score of 70 are proposed from `app/kb/column_hints.md` and must be confirmed before load. Ambiguous dates are read day-month-year first.
  * *Reason:* No model key is configured. The hint file is the fallback the spec would hand to a model. The saved method for that path is `llm`, which is the spec's name for the non-fuzzy path.
  * *Rejected:* Calling a hosted model during ingestion. Reading ambiguous dates as month-day-year.
  * *Files affected:* `app/packages/ingest/`, `app/kb/column_hints.md`.
* **Decision 19 (2026-11-08):** The first screen is a Next.js app at `app/apps/web`, using the shadcn/ui `base-nova` preset. It is one route. It shows the three panes and does not call SQL or ingest.
  * *Reason:* The user asked for the UI first, with shadcn, before the API.
  * *Rejected:* Scaffolding at the repo root. `shadcn init` created a nested `.git` in `app/apps/web`; that directory was removed so Nexus stays one local repository.
  * *Files affected:* `app/apps/web/`.
* **Decision 20 (2026-11-08):** `runs` stores `workspace_id`. `feedback` and `eval_results` are created with the v2 columns.
  * *Reason:* Chat is per data room. The v2 column list for `runs` has no workspace column, and a trace from one room must not be mixed with another.
  * *Rejected:* Leaving runs unscoped.
  * *Files affected:* `app/infra/week3.sql`, `app/infra/schema.sql`, `app/apps/api/main.py`.
* **Decision 21 (2026-11-08):** The chat planner runs SQL only when the question matches the golden set. Anything else is refused when a required column is empty, or left unanswered. No model is called.
  * *Reason:* No provider has been chosen. Inventing SQL for a free-form question would put numbers on screen that the golden set does not stand behind.
  * *Rejected:* Calling a hosted model. Generating SQL from keywords.
  * *Files affected:* `app/packages/agent/loop.py`, `app/apps/api/main.py`.