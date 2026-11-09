# Architecture

Nexus is a Retail Data Room Copilot. An analyst creates a Data Room, uploads a retail sales spreadsheet and optional documents, and asks questions in one chat. A single LangGraph agent answers numeric questions with read-only SQL and text questions with pgvector search, and shows its steps live. A deterministic checker verifies every number before the answer is shown.

Incorporated from the v2 product document (8 November 2026). Effort estimates, metric targets, and stack choices in that document are the author's suggestions, not Bain requirements. Rationale for the structural choices is in `decisions.md`.

## Users and scope

Primary user: a consulting analyst or associate who receives Excel or CSV data and needs fast, defensible answers.

Goals: answer commercial questions with traceable numbers; reject or repair bad files and explain why; show the agent's work; measure quality with a golden set; run locally and deploy cheaply to Azure.

v1 domain: retail pricing and promotion, category and product profitability, and customer analytics. The same shape can hold PE diligence and survey data. v1 is one canonical table shape (`sales_clean`) plus optional documents.

Non-goals for v1: arbitrary spreadsheets (payroll, wide pivots, free-form reports); multi-tenant auth, SSO, and role hierarchies; write access, automated pricing, and forecasting; web search on the default path; hybrid BM25 plus a cross-encoder reranker.

Example questions: which sub-categories lose money, and is it linked to discounts; top 10 customers by profit and their share of total profit; which promotions lost money last quarter; summarise what an uploaded category report says about private label.

The project is evidence for four Bain Capability Network roles: Capabilities Tech Hub (Commercial Excellence, Agentic AI), Retail CoE (Associate, AI Data Engineer), PEG Alpha (Associate, AI Data Engineer), and PEG (Associate, AI Solutions Engineer). Core covers the agent, RAG, FastAPI plus Postgres, evaluation, ingestion, Docker/CI, and the Next.js UI. Add-ons are listed in `roadmap.md`. Pick one or two; do not build all of them.

## Tech stack

| Layer | v1 | Later, not v1 |
|---|---|---|
| UI | Next.js, TypeScript, Tailwind, shadcn/ui, Recharts, SSE | Auth, TanStack Table |
| API | FastAPI, Pydantic, BackgroundTasks | Redis, Celery |
| Agent | LangGraph, one loop | Azure AI Agent Service comparison |
| Database | PostgreSQL + pgvector, same instance | Snowflake adapter, Azure AI Search |
| Graph | none | Neo4j product hierarchy |
| Processing | pandas, SQL | PySpark for a large file |
| Ingestion jobs | BackgroundTasks | Airbyte or Airflow |
| Models | one hosted provider + one local (Ollama/vLLM) | OpenAI/Anthropic switch, reranker |
| Observability | `runs` table; Langfuse optional | — |
| Packaging | Docker Compose, pytest, GitHub Actions | Azure Container Apps or App Service, Blob storage |

Week 1 uses the existing local PostgreSQL 18 and pgAdmin. The database name is `nexus_db`. See Decisions 5 and 14. DDL is `backend/db/changesets/001_initial_schema.sql`; the Superstore seed loader is `backend/db/seeds/load_superstore.py`. That step creates `workspaces`, `uploads`, and `sales_clean` only. `sales_clean.id` is a surrogate key because an order line is not unique on the business columns. Quantity, unit price, discount, cost, profit, and channel are nullable; `datasets/Superstore/Superstore.csv` does not contain them.

## UI

One screen, one route, at `frontend/`. The conversation is the screen. A quiet sidebar holds the data room: the file, rows set aside, and conversation threads. The query, the row count, and the chart stay behind "Show tool execution" on an answer.

The palette is the one in `frontend/app/globals.css`: a white field, warm stone text, a red primary, and square corners (`--radius: 0`). Dark mode is the same hues inverted. Type is JetBrains Mono. The stack is Next.js 16, TypeScript, Tailwind, and shadcn/ui with `@base-ui/react`.

File ingestion occurs completely in-chat:
1. Dragging a `.csv` or `.xlsx` into the chat creates an in-stream upload card.
2. The agent displays a single quiet pulsating tool line at a time (`animate-ping` + `animate-pulse`), inspecting file structure and column profiles in <1.0s.
3. The schema proposal renders inline with:
   - Markdown-rendered grain description with hairline code chips and inline click-to-edit.
   - Column approval table using shadcn `ScrollArea`, `Table`, `Badge`, and `DropdownMenu` for type and role adjustments.
   - 10-row preview with hairline borders.
4. Clicking "Approve & create table" immediately creates a custom PostgreSQL table (`user_data.ds_*`) and streams rows via binary COPY in ~500ms.
5. Nexus greets the user using the friendly dataset label (e.g. `Superstore`) with clickable, retail-intelligent question chips prioritizing commercial metrics (revenue, sales, profit) against dimensions (category, segment, region).
6. Assistant answers stream markdown tokens, tool calls, and AST-guarded SQL under `nexus_reader` RLS, with deterministic verification via `checker.py`.

## Data model

The persistent database layer is hosted in PostgreSQL (`nexus_db`).

| Table | Key columns | Purpose |
|---|---|---|
| `workspaces` | `id`, `name`, `created_at` | Data room isolation boundary |
| `uploads` | `id`, `workspace_id`, `original_name`, `stored_name`, `sha256`, `size`, `status`, `schema_proposal`, `custom_table_name` | Staged and registered tabular uploads |
| `datasets` | `id`, `workspace_id`, `upload_id`, `table_name`, `table_label`, `grain`, `grain_key_columns`, `row_count`, `header_hash` | Approved custom dataset registry |
| `dataset_columns` | `id`, `dataset_id`, `column_name`, `type`, `role`, `description`, `unit`, `null_rate`, `date_format` | Per-dataset typed column catalog |
| `user_data.ds_*` | `row_id`, `workspace_id`, `upload_id`, *dynamically typed columns* | Custom dataset tables isolated via PostgreSQL RLS |
| `agent_events` | `id`, `workspace_id`, `agent_kind`, `run_id`, `upload_id`, `seq`, `stage`, `event_type`, `label`, `payload`, `created_at` | Unified real-time agent step and event ledger |
| `runs` | `id`, `workspace_id`, `upload_id`, `agent_kind`, `question`, `plan`, `answer`, `checker_result`, `python_results`, `latency_ms`, `model` | Unified execution audit log |
| `eval_results` | `id`, `run_id`, `question_id`, `metrics` | Golden set test runs |
| `feedback` | `id`, `run_id`, `rating`, `comment` | User quality ratings |
| `sales_clean` *(deprecated)* | `workspace_id`, `upload_id`, 15 canonical columns, `attributes` JSONB | Retained exclusively for benchmark evaluation (`golden_set.json`) |
| `column_mapping` *(deprecated)* | `upload_id`, `source_column`, `canonical_column` | Retained for historical schema migration records |
| `quarantine` *(deprecated)* | `upload_id`, `row_number`, `reason`, `raw_json` | Retained for historical reject audits |
| `feedback` | `run_id`, `rating`, `reason` | `run_id` → `runs` |
| `eval_results` | `eval_run_id`, `question_id`, `passed`, `metrics_json` | Not linked to `runs` in the listed columns |

`run_sql` reads `sales_clean` only. A row is in domain if it has a date, a customer or product identifier, and a revenue or quantity measure. Cost and profit are optional. Margin questions are refused when cost or profit is absent.

The spec's column list for `documents` / `chunks` still has no `workspace_id`. `runs.workspace_id` was added (Decision 20). That documents gap is unresolved in `active-context.md`.

## Ingestion

Order: file safety, structure, schema architect analysis, human schema approval, row validation, COPY stream commit.

1. **File safety — reject.** Allow csv and xlsx. Sniff content. Cap size (50 MB). Store under a generated name. Reject macro-enabled files. Parse safely.
2. **Structure — reject or ask.** Non-empty, more than one column, row and column caps, header-row detection, multi-sheet handling.
3. **Schema Architect — native in-chat participant.** Every uploaded .csv/.xlsx goes directly to the Schema Architect. The agent streams its inspection steps live in chat (`list_columns`, `profile_column`, `test_parse`, `detect_date_format`, `check_uniqueness`, `sample_rows`), proposes table grain and column roles/types, and checks schema memory against previously approved hashes.
4. **Human Schema Approval.** The user reviews the compact inline proposal card (grain, target name, type, role, include/exclude toggle), edits with server-side validation, and clicks Approve. No table is created without explicit user approval.
5. **Row validation & COPY load.** Validated rows are loaded into PostgreSQL `user_data.<table_name>` via streaming COPY. Anomalies are quarantined with download reports preserved.
6. **Handoff to Nexus.** Upon table creation, Schema Architect hands off to Nexus with a deterministic summary and clickable question chips derived from column roles.

*Note on `sales_clean`:* The legacy column-mapping flow and `needs_confirmation` state are completely removed from the upload experience. `sales_clean` is preserved exclusively as seeded benchmark data (e.g. Superstore) until formally retired in a future release.

## Agent

Tools: `get_schema` (columns, types, mapping, samples); `run_sql` (SELECT only on that workspace's clean data); `search_docs` (pgvector, metadata filter, page numbers); `read_kb` (one knowledge-base file by path); `run_python` (pandas/sklearn for segmentation, correlation, cohorts); `web_search` optional and off by default.

Loop, as built: one LangGraph thread per workspace. The model sees the conversation and chooses the next tool. The tools in the graph are `get_schema`, `run_sql`, `read_kb`, and `run_python` (in `backend/agent/tools/`). `search_docs` and `web_search` are not wired.

`run_python` executes deterministic math (CAGR, Pearson correlation, cohort retention, percentage difference comparisons) in an isolated subprocess. The execution boundary runs in a scrubbed environment with no network access, no database credentials, a 10-second timeout, and a 256MB memory cap. An AST allowlist serves as a strict syntactic filter against hazardous builtins (open, exec, eval, __import__, os, sys, subprocess, socket), with the isolation boundary enforced by the OS subprocess. Indentation and code fences from LLM outputs are normalized via `clean_code()`. Each step of a question, and the code that implements it, is in `context/agent/`. Start at `context/agent/README.md`.

The checker is deterministic Python. It is not another model. LLM-as-judge is allowed for narrative quality only, never for numbers.

`run_sql` connects as the non-superuser role `nexus_reader`. A row-level policy shows only the workspace named by the transaction setting `app.workspace_id`. The tool allows one `SELECT` against `sales_clean`, then runs it inside a read-only transaction with a 5 second timeout and a 25 row preview cap (up to 200 row fetch cap). The password for that role stays in `.env` and is not committed. The checker compares every number in a draft against the union of SQL result rows and `run_python` numeric results. It normalizes percentages versus fractions, applies precision-based tolerances, and exempts non-claims (years, dates, ordinals, Top N, code spans). `backend/eval/runner.py` runs the 30-question golden set (including SQL, Python math, refusals, and mapping accuracy) and exits non-zero below the targets in the v2 document. GitHub Actions running that script on push is Week 4.

Knowledge base (markdown, versioned with the repo):

```text
backend/kb/README.md
backend/kb/metrics.md          # margin, discount rate, AOV, churn, RFM
backend/kb/column_hints.md
backend/kb/playbooks/discount_leakage.md
backend/kb/playbooks/segmentation_rfm.md
backend/kb/playbooks/product_profitability.md
backend/kb/caveats.md
```

Prompts live in versioned files with typed structured outputs. A provider interface can swap OpenAI, Anthropic, or a local model. Comparing them on the golden set is the PEG AI Solutions add-on, not the Week 1 path.

## API

| Endpoint | Method | Purpose |
|---|---|---|
| `/workspaces` | POST, GET | Create and list Data Rooms |
| `/workspaces/{id}` | GET | One room: uploads, health, quarantine, latest mapping |
| `/workspaces/{id}/uploads` | POST | Upload a file; return upload id |
| `/uploads/{id}/events` | GET SSE | Ingestion status |
| `/uploads/{id}/mapping` | GET, PUT | Read the proposal; save edits and confirm |
| `/uploads/{id}/health` | GET | Health report and quarantine download |
| `/workspaces/{id}/chat` | POST SSE | Ask; stream steps and the answer |
| `/runs/{id}/feedback` | POST | Thumbs and reason |
| `/eval/runs` | GET, POST | List and trigger eval runs |
| `/results/{id}/export` | GET | CSV export |

Chat events: `step` (tool, status), `sql` (query, row count), `source` (document, page, snippet), `token`, `check` (verified or caveats), `done` (run id, cost, latency), `error`.

## Evaluation

Golden set of 25 to 50 verified questions across Superstore, Online Retail II, and the project's documents. CI reruns it on every push and fails the build if scores drop past a threshold. Record before/after numbers for the checker and for model swaps.

| Metric | Target |
|---|---|
| SQL correctness vs hand-verified answers | 85% or higher |
| Numeric faithfulness (answer numbers traceable to tool output) | 98% or higher |
| Retrieval hit rate (expected passage in top-k) | 85% or higher |
| Refusal accuracy | 90% or higher |
| Mapping accuracy | 90% or higher |
| Latency and cost | Report p50/p95, tokens, cost |
| Safety (prompt-injection cells, write-query attempts) | 0 successful |

## Security

Per-workspace isolation in queries and retrieval. Secrets live in environment variables or a secrets manager. Uploads are size- and type-limited, stored under generated names, and parsed in a sandbox. Rate-limit the API. Audit questions, SQL, and uploads. The published demo uses public or synthetic data only.

Guardrails for tools and modules are in `agents.md`.

## Repository map

The codebase is cleanly divided at root between frontend and backend:

| Role | Path | Description |
|---|---|---|
| UI | `frontend/` | Next.js 16 app with Tailwind, shadcn/ui, JetBrains Mono |
| Backend API | `backend/main.py`, `backend/api/` | FastAPI entry point, routers (`routers/`), services (`services/`) |
| Agent | `backend/agent/` | Graph, state, `nodes.py`, `tools/` (`get_schema.py`, `run_sql.py`, `read_kb.py`, `run_python.py`), `checker.py`, `sandbox.py` |
| Ingest | `backend/ingest/` | Modular pipeline: `reader.py`, `mapping.py`, `store.py`, `pipeline.py` |
| Knowledge Base | `backend/kb/` | Markdown reference playbooks, metrics definitions |
| Evaluation | `backend/eval/` | Single-source `golden_set.json` and `runner.py` |
| Database | `backend/db/` | Changesets (`changesets/`) and seeds (`seeds/`) |
| Tests | `backend/tests/` | Pytest suite (`test_*.py`, `conftest.py`) |
| Context / Docs | `context/` | Project architecture, decisions log, design language |
| Datasets | `datasets/` | Superstore CSV and sample files |

## Datasets

Stand-ins, not client data. Check the licence of any Superstore copy before publishing.

| Source | Use | Limitation |
|---|---|---|
| Superstore Sales | Primary set for discount and profit questions | About 10k rows |
| Online Retail II (UCI) | Excel upload demo and segmentation (UK, Dec 2009–Dec 2011) | No cost or profit |
| Olist (Kaggle) | Multi-table joins and a larger ETL demo | No discount or profit column |
| Self-written retail PDFs | RAG demo | Synthetic |
| Synthetic survey file | Survey-validation add-on | Synthetic |
