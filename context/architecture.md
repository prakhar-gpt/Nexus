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

One screen, one route, at `frontend/`. The conversation is the screen. A quiet sidebar holds the data room: the file, a confirmation when a column is uncertain, rows set aside, and the golden-set score. The query, the row count, and the chart stay behind "Show the query" on an answer. There is no third pane and no document chip. Decision 23.

The palette is the one in `frontend/app/globals.css`: a white field, warm stone text, a red primary, and square corners. Dark mode is the same hues inverted. It does not follow the operating system theme. Type is JetBrains Mono. The stack is still Next.js, TypeScript, Tailwind, and the shadcn `base-nova` preset (Decision 19). Recharts loads only when a query is opened.

The screen talks to the FastAPI app in `backend/` (`backend/main.py`). Assistant answers are rendered as markdown while the tokens arrive. A streamed token keeps its spaces. A question streams the tools the agent chose as each one starts, then the answer tokens as they are written, then the checker. Opening a data room reloads the last 20 turns from `runs`. A failed upload, a dropped stream, a mapping that does not save, and a rating that does not save each surface as a short error. They do not leave the control looking successful.

## Data model

Nine tables. `workspaces` is the Data Room.

| Table | Key columns | Links |
|---|---|---|
| `workspaces` | `id`, `name`, `created_at` | Root |
| `uploads` | `id`, `workspace_id`, `original_name`, `stored_name`, `sha256`, `size`, `status`, `created_at` | `workspace_id` → `workspaces` |
| `column_mapping` | `upload_id`, `source_column`, `canonical_column`, `confidence`, `method` (`fuzzy` or `llm`), `confirmed_by_user` | `upload_id` → `uploads` |
| `sales_clean` | `workspace_id`, `upload_id`, `order_date`, `customer_id`, `product_id`, `quantity`, `revenue`, `unit_price`, `discount_pct`, `cost`, `profit`, `segment`, `region`, `category`, `sub_category`, `channel` | Both `workspace_id` and `upload_id` |
| `sales_clean` | `workspace_id`, `upload_id`, ..., `attributes` (JSONB) | Both `workspace_id` and `upload_id` |
| `upload_attribute_schema` | `upload_id`, `key`, `inferred_type`, `null_rate`, `sample_values` | `upload_id` → `uploads` |
| `quarantine` | `upload_id`, `row_number`, `reason`, `raw_json` | `upload_id` → `uploads` |
| `documents` / `chunks` | `doc_id`, `chunk_id`, `text`, `embedding`, `page`, `section`, `metadata` | `chunk_id` under `doc_id` |
| `runs` | `id`, `workspace_id`, `question`, `plan`, `sql_list`, `answer`, `checker_result`, `latency_ms`, `tokens`, `cost`, `model`, `created_at` | `workspace_id` → `workspaces` |
| `feedback` | `run_id`, `rating`, `reason` | `run_id` → `runs` |
| `eval_results` | `eval_run_id`, `question_id`, `passed`, `metrics_json` | Not linked to `runs` in the listed columns |

`run_sql` reads `sales_clean` only. A row is in domain if it has a date, a customer or product identifier, and a revenue or quantity measure. Cost and profit are optional. Margin questions are refused when cost or profit is absent.

The spec's column list for `documents` / `chunks` still has no `workspace_id`. `runs.workspace_id` was added (Decision 20). That documents gap is unresolved in `active-context.md`.

## Ingestion

Order: file safety, structure, domain fit, row validation, text safety.

1. **File safety — reject.** Allow csv and xlsx. Sniff content. Cap size. Store under a generated name. Reject macro-enabled files. Parse in a sandbox.
2. **Structure — reject or ask.** Non-empty, more than one column, row and column caps, header-row detection, multi-sheet handling.
3. **Domain fit — reject with what is missing.** After mapping, require a date-like column, revenue or quantity, and an identifier, at adequate confidence.
4. **Row validation — quarantine.** Date parse, numeric types, negatives, duplicates, impossible discounts. Keep `row_number`, `reason`, and `raw_json`.
5. **Text safety — sanitise.** Cells are data. On any export, prefix cells that start with `=`, `+`, `-`, or `@`. Never pass cell or document text to the model as instructions.

Mapping: normalise the header (lowercase, strip, collapse spaces); RapidFuzz against the canonical names (`order_date`, `sales`, `profit`, `discount_pct`, `customer_id`, `product_id`, `quantity`, `unit_price`, and the rest of `sales_clean`); auto-map at 70% or above; below 70%, propose from `backend/kb/column_hints.md` and require confirmation before load. No model key is configured, so that fallback does not call a model. The code lives in `backend/ingest/` (`reader.py`, `mapping.py`, `store.py`, `pipeline.py`). Dates are read as day-month-year when the text is ambiguous. `customer_id` or `product_id` satisfies the identifier rule, and `revenue` or `quantity` satisfies the measure rule.

Six test files and their expected results are in `roadmap.md`.

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
