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

Week 1 uses the existing local PostgreSQL 18 and pgAdmin. The database name is `nexus_db`. See Decisions 5 and 14. DDL is `app/infra/schema.sql`; the Superstore seed loader is `app/infra/load_superstore.py`. That step creates `workspaces`, `uploads`, and `sales_clean` only. `sales_clean.id` is a surrogate key because an order line is not unique on the business columns. Quantity, unit price, discount, cost, profit, and channel are nullable; `datasets/Superstore/Superstore.csv` does not contain them.

## UI

One dashboard, three panes. No multi-page routing.

- **Left — Data & Health.** Drag-and-drop upload, per-file progress (safety, structure, profiling, mapping), mapping confirmation, data health, quarantine list, quarantine CSV download.
- **Center — Chat.** Message box, suggested questions, streaming answer, verified and caveat badges, source chips (SQL, doc passage, row count), thumbs up/down, CSV export.
- **Right — Trace & Eval, collapsible.** Live steps (schema, KB read, SQL, doc search, checker), timing, verification result; a tab for golden-set score, latency, cost, and failure types.

Show uncertainty. Every number links to its SQL and row count. Answer first, trace one click away. Design empty, loading, and error states for every pane.

The screen is `app/apps/web`, one route, shadcn/ui preset `base-nova` (Decision 19). It talks to the FastAPI app in `app/apps/api`. A question streams schema, SQL, the checker, and the answer. The SQL is one of the golden-set questions (Decision 21). The document chip stays inactive.

## Data model

Nine tables. `workspaces` is the Data Room.

| Table | Key columns | Links |
|---|---|---|
| `workspaces` | `id`, `name`, `created_at` | Root |
| `uploads` | `id`, `workspace_id`, `original_name`, `stored_name`, `sha256`, `size`, `status`, `created_at` | `workspace_id` → `workspaces` |
| `column_mapping` | `upload_id`, `source_column`, `canonical_column`, `confidence`, `method` (`fuzzy` or `llm`), `confirmed_by_user` | `upload_id` → `uploads` |
| `sales_clean` | `workspace_id`, `upload_id`, `order_date`, `customer_id`, `product_id`, `quantity`, `revenue`, `unit_price`, `discount_pct`, `cost`, `profit`, `segment`, `region`, `category`, `sub_category`, `channel` | Both `workspace_id` and `upload_id` |
| `quarantine` | `upload_id`, `row_number`, `reason`, `raw_json` | `upload_id` → `uploads` |
| `documents` / `chunks` | `doc_id`, `chunk_id`, `text`, `embedding`, `page`, `section`, `metadata` | `chunk_id` under `doc_id` |
| `runs` | `id`, `question`, `plan`, `sql_list`, `answer`, `checker_result`, `latency_ms`, `tokens`, `cost`, `model`, `created_at` | No workspace column listed |
| `feedback` | `run_id`, `rating`, `reason` | `run_id` → `runs` |
| `eval_results` | `eval_run_id`, `question_id`, `passed`, `metrics_json` | Not linked to `runs` in the listed columns |

`run_sql` reads `sales_clean` only. A row is in domain if it has a date, a customer or product identifier, and a revenue or quantity measure. Cost and profit are optional. Margin questions are refused when cost or profit is absent.

The spec requires workspace-scoped retrieval and per-workspace isolation, and the listed columns for `documents` / `chunks` and `runs` do not include `workspace_id`. That gap is unresolved in `active-context.md`.

## Ingestion

Order: file safety, structure, domain fit, row validation, text safety.

1. **File safety — reject.** Allow csv and xlsx. Sniff content. Cap size. Store under a generated name. Reject macro-enabled files. Parse in a sandbox.
2. **Structure — reject or ask.** Non-empty, more than one column, row and column caps, header-row detection, multi-sheet handling.
3. **Domain fit — reject with what is missing.** After mapping, require a date-like column, revenue or quantity, and an identifier, at adequate confidence.
4. **Row validation — quarantine.** Date parse, numeric types, negatives, duplicates, impossible discounts. Keep `row_number`, `reason`, and `raw_json`.
5. **Text safety — sanitise.** Cells are data. On any export, prefix cells that start with `=`, `+`, `-`, or `@`. Never pass cell or document text to the model as instructions.

Mapping: normalise the header (lowercase, strip, collapse spaces); RapidFuzz against the canonical names (`order_date`, `sales`, `profit`, `discount_pct`, `customer_id`, `product_id`, `quantity`, `unit_price`, and the rest of `sales_clean`); auto-map at 70% or above; below 70%, propose from `app/kb/column_hints.md` and require confirmation before load. No model key is configured, so that fallback does not call a model. The code lives in `app/packages/ingest/`. Dates are read as day-month-year when the text is ambiguous. `customer_id` or `product_id` satisfies the identifier rule, and `revenue` or `quantity` satisfies the measure rule.

Six test files and their expected results are in `roadmap.md`.

## Agent

Tools: `get_schema` (columns, types, mapping, samples); `run_sql` (SELECT only on that workspace's clean data); `search_docs` (pgvector, metadata filter, page numbers); `read_kb` (one knowledge-base file by path); `run_python` (pandas/sklearn for segmentation, correlation, cohorts); `web_search` optional and off by default.

Loop: read the question, `get_schema`, `read_kb` per the KB routing rules; plan and refuse if required columns are missing; `run_sql` and/or `search_docs`; optional `run_python`; draft using only numbers present in tool outputs; the checker compares every number and claim to those outputs; emit the answer, SQL, row counts, sources, and caveats or a refusal.

The checker is deterministic Python. It is not another model. LLM-as-judge is allowed for narrative quality only, never for numbers.

`run_sql` connects as the non-superuser role `nexus_reader`. A row-level policy shows only the workspace named by the transaction setting `app.workspace_id`. The tool allows one `SELECT` against `sales_clean`, then runs it inside a read-only transaction with a 5 second timeout and a 200 row cap. The password for that role stays in `.env` and is not committed. The checker compares every number in a draft to the SQL result. `app/eval/runner.py` runs the 25-question golden set and exits non-zero below the targets in the v2 document. GitHub Actions running that script on push is Week 4.

Knowledge base (markdown, versioned with the repo):

```text
kb/README.md
kb/metrics.md          # margin, discount rate, AOV, churn, RFM
kb/column_hints.md
kb/playbooks/discount_leakage.md
kb/playbooks/segmentation_rfm.md
kb/playbooks/product_profitability.md
kb/caveats.md
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

Application code stays under `app/`. This `context/` folder is the project brain the v2 tree called `docs/`. Sample data already on disk is `datasets/Superstore/Superstore.csv`, not `data/samples/`.

| v2 path | Nexus path |
|---|---|
| `apps/web` | `app/apps/web` |
| `apps/api` | `app/apps/api` |
| `packages/ingest`, `packages/agent`, `packages/rag` | `app/packages/ingest`, `app/packages/agent`, `app/packages/rag` |
| `kb`, `eval` | `app/kb`, `app/eval` |
| `infra` | `app/infra` |
| `data/samples` | `datasets/` until a loader exists |

## Datasets

Stand-ins, not client data. Check the licence of any Superstore copy before publishing.

| Source | Use | Limitation |
|---|---|---|
| Superstore Sales | Primary set for discount and profit questions | About 10k rows |
| Online Retail II (UCI) | Excel upload demo and segmentation (UK, Dec 2009–Dec 2011) | No cost or profit |
| Olist (Kaggle) | Multi-table joins and a larger ETL demo | No discount or profit column |
| Self-written retail PDFs | RAG demo | Synthetic |
| Synthetic survey file | Survey-validation add-on | Synthetic |
