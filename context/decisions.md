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
* **Decision 22 (2026-11-08):** The agent chooses its next tool. The route is not fixed. Chat history is the workspace thread: prior turns stay in memory, and the last eight questions and answers are reloaded from `runs` after a restart. The first configured key is used, in order Groq `openai/gpt-oss-120b`, OpenRouter, then DeepSeek. This supersedes the fixed golden-set planner in Decision 21. The SQL guard and the deterministic checker stay.
  * *Reason:* A follow-up only makes sense if the agent can see the earlier turn and decide what to run. The golden set remains the eval, not the router.
  * *Rejected:* Keeping the four-node schema, plan, SQL, checker sequence. Sending the whole conversation from the browser as the source of truth.
  * *Files affected:* `app/packages/agent/graph.py`, `app/packages/agent/model.py`, `app/packages/agent/prompts/system.md`, `app/apps/api/main.py`, `app/apps/web/components/dashboard.tsx`.
* **Decision 23 (2026-11-08):** The screen is a chat. The data room stays in a sidebar. The query, the chart, and the golden-set score open on demand. The palette is warm ivory and clay, and it does not follow the operating system theme.
  * *Reason:* A three-column dashboard put health, trace, eval, and a document chip on screen at once. A chat does not. The black-and-white theme made that density harsher.
  * *Rejected:* Keeping the right-hand trace pane. Rendering a document chip before document search exists. Following the system theme into pure black.
  * *Files affected:* `app/apps/web/`, `context/architecture.md`.
* **Decision 24 (2026-11-08):** The screen uses the supplied theme tokens: white field, warm stone text, red primary, square corners. Dark mode uses the matching inverted set.
  * *Reason:* The user replaced the earlier ivory and clay palette with this one.
  * *Rejected:* Keeping the previous oklch values.
  * *Files affected:* `app/apps/web/app/globals.css`.
* **Decision 25 (2026-11-08):** Chat streams each tool as it starts, then the answer tokens as they are written. The screen shows one status line per tool while it runs.
  * *Reason:* The previous stream waited for the whole graph, then sent every event at once. A running tool was invisible until the answer arrived.
  * *Rejected:* Buffering the answer and dumping it in one token event. Showing the tool name only after the checker.
  * *Files affected:* `app/packages/agent/graph.py`, `app/packages/agent/model.py`, `app/apps/api/main.py`, `app/apps/web/components/dashboard.tsx`, `app/apps/web/components/chat-pane.tsx`.
* **Decision 26 (2026-11-08):** Streamed tokens keep their spaces, and the answer is a sentence rather than a field dump. The finished answer in the `done` event replaces the live text so it matches what a refresh loads.
  * *Reason:* Each model token arrives with a leading space. Stripping that space glued the words together, so markdown such as `**Total revenue:**` only rendered after a refresh loaded the stored sentence. The model was also copying tool output like `subcategories=17`.
  * *Rejected:* Leaving the live text as the concatenation of stripped tokens. Teaching the model to answer with `name=value`.
  * *Files affected:* `app/packages/agent/graph.py`, `app/packages/agent/prompts/system.md`, `app/apps/api/main.py`, `app/apps/web/components/dashboard.tsx`.
* **Decision 27 (2026-11-08):** Each step of a question has its own file under `context/agent/`. `architecture.md` keeps the product shape and points there.
  * *Reason:* The loop now spans the graph, the SQL guard, the stream, and the screen. A later session needs that path in order, without pasting `graph.py` into the architecture note.
  * *Rejected:* One long section inside `architecture.md`. Copying the source files into `context/`.
  * *Files affected:* `context/agent/`, `context/INDEX.md`, `context/architecture.md`, `context/agents.md`.
* **Decision 28 (2026-11-08):** Tool execution indicators stream as one single pulsating line at a time, and disappear with no persistence once the answer text begins or stream finishes.
  * *Reason:* Multiple stacked static tool lines cluttered the chat above the finished answer.
  * *Rejected:* Showing all tool call steps permanently above the assistant response.
  * *Files affected:* `app/apps/web/components/chat-pane.tsx`, `app/apps/web/components/dashboard.tsx`.
* **Decision 29 (2026-11-08):** `psql` subprocess invocations on Windows enforce `encoding="utf-8"`.
  * *Reason:* Windows defaults subprocess text mode to `cp1252`, crashing with `UnicodeEncodeError` on narrow non-breaking spaces (`\u202f`), curly quotes, and dashes emitted by hosted LLMs when persisting runs.
  * *Rejected:* Leaving subprocess encoding to system default code page.
  * *Files affected:* `app/packages/agent/db.py`, `app/infra/load_superstore.py`.
* **Decision 30 (2026-11-08):** The number checker is context-aware (recognizing numbers in user prompts, earlier conversation turns, executed SQL text, and ordinals like 8th/26th), and clarification questions do not trip the checker. The agent is prompted to actively ask clarifying questions when date ranges or required filters are ambiguous.
  * *Reason:* The checker previously flagged prompt dates or query limits as untraced hallucinations. The agent also silently guessed years or refused when a year was omitted.
  * *Rejected:* Blank check on all numbers without context, and silently guessing dates.
  * *Files affected:* `app/packages/agent/checker.py`, `app/packages/agent/graph.py`, `app/packages/agent/prompts/system.md`, `context/agent/07-checker.md`.
* **Decision 31 (2026-11-08):** Add explicit role & visualization guardrails in `system.md`.
  * *Reason:* The agent was generating raw Mermaid syntax blocks and pseudo-charts when asked to "render chart". Native interactive charts already exist in the UI via Recharts under "Show the query".
  * *Rejected:* Allowing the LLM to output arbitrary text diagrams, Mermaid blocks, or scripts.
  * *Files affected:* `app/packages/agent/prompts/system.md`.
* **Decision 32 (2026-11-08):** Production-grade backend refactor with strict separation of concerns.
  * *Reason:* `graph.py` (440 lines) and `main.py` (464 lines) had accumulated tool declarations, handlers, nodes, routers, schemas, services, and route definitions into large monolithic files.
  * *Rejected:* Leaving the monolithic files in place.
  * *Files affected:* `app/packages/agent/` (`state.py`, `formatting.py`, `tools/`, `nodes/`, `graph.py`), `app/apps/api/` (`schemas.py`, `sse.py`, `services/`, `routers/`, `main.py`).
* **Decision 33 (2026-11-08):** Planned deterministic Python math tool (`run_python`).
  * *Reason:* Pure SQL arithmetic is insufficient for complex multi-step financial modeling, compound growth (CAGR), projections, and statistical correlations. Numbers returned by `run_python` will be recorded in state and whitelisted by `checker.py` as verified figures.
  * *Rejected:* Allowing LLM to do mental arithmetic in answer text without deterministic tool execution.
  * *Files to be affected:* `app/packages/agent/tools/`, `app/packages/agent/nodes/`, `app/packages/agent/checker.py`, `app/packages/agent/prompts/system.md`.
* **Decision 34 (2026-11-08):** Planned dynamic dataset column support via canonical core anchors (`order_date`, `revenue`/`quantity`) plus an `attributes JSONB` payload column.
  * *Reason:* Real-world commercial datasets contain arbitrary domain-specific columns (e.g. `carrier`, `ad_spend`, `plan_tier`). Storing unmapped non-canonical columns in a JSONB dictionary allows dynamic SQL querying (`attributes->>'field'`) while preserving the strict retail domain guardrails (date + financial measure) preventing scope creep into arbitrary non-commercial files.
  * *Rejected:* Complete unstructured schema-free ingestion of any file (hospital, sports, payroll) without domain validation; and rigidly rejecting files with non-canonical attributes.
  * *Files to be affected:* `app/infra/schema.sql`, `app/packages/ingest/clean.py`, `app/packages/agent/tools/handlers.py`.
* **Decision 35 (2026-11-08):** Implemented multi-thread conversations per workspace and prominent Nexus UI branding.
  * *Reason:* A data room (workspace) contains heavy uploaded spreadsheets, quarantine records, and schema mappings. Forcing a new workspace for every conversation forced redundant re-uploading and re-mapping of data. Workspaces now contain multiple independent conversation threads (`thread_id`), allowing analysts to run separate topical analyses within the same data room.
  * *Rejected:* Creating a new data room workspace for every new conversation.
  * *Files affected:* `app/apps/api/routers/workspaces.py`, `app/apps/api/schemas.py`, `app/apps/api/services/workspace_service.py`, `app/apps/api/services/chat_service.py`, `app/packages/agent/graph.py`, `app/apps/web/components/dashboard.tsx`, `app/apps/web/components/data-pane.tsx`, `app/apps/web/lib/api.ts`.
