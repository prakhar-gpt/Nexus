# Roadmap (4-Week Build)

Part-time estimate from the v2 document: 3 to 4 weeks. If time runs short, ship Weeks 1–3 plus a minimal UI. Cut in this order: Neo4j, PySpark, Redis, PDF support. Keep the SQL path, the checker, the Eval panel, and upload validation.

Week 4 Docker Compose packages the application. The database stays the existing local PostgreSQL (Decision 5) until a later decision says otherwise.

## Week 1 — complete

Postgres + Superstore loaded into `sales_clean`. Read-only `run_sql`. A 25-question golden set. The Python number checker. A CI eval script.

## Week 2 — complete

Ingestion: parsing, header detection, RapidFuzz mapping with LLM fallback, quarantine. All six test files pass.

| File | Expected result |
|---|---|
| 1 Clean sales table | Accepted, auto-mapped |
| 2 Junk rows above the header | Header detected, or the user is asked |
| 3 Messy names and text numbers | Mapped with confirmation, then cleaned |
| 4 Empty or single-column file | Rejected with a reason |
| 5 Unrelated data (payroll) | Rejected at domain fit |
| 6 Formula-like and prompt-injection cells | Stored as inert data; the agent is unaffected |

## Week 3 — screen and API connected

Single-dashboard Next.js UI. FastAPI SSE. The screen is a chat with the data room in a sidebar. The agent chooses its tools, and the room reloads its chat history. Document search is not built.

## Week 4

One role-specific add-on, chosen from the list below. Docker Compose. GitHub Actions running eval on push. A two-minute demo.

Demo beats to cover: a clean upload and a bad upload with its quarantine report; a mapping confirmation; a losing-sub-category question with trace, chart, SQL chip, and verified badge; a refusal; a document question with its source passage; Eval scores before and after the checker.

Talking points live with that demo: why SQL is the source of truth, where the checker changed a number, local versus hosted model cost and latency, what would change at CoE scale, and how tests kept the AI-assisted build honest.

## Add-ons — pick one or two

The choice depends on the first role, which is still open (`active-context.md`).

| Add-on | Best-fit role | Effort |
|---|---|---|
| Survey validation (speeders, straight-liners, duplicates) | PEG Alpha | 1–2 days |
| Provider switch and model comparison on the golden set | PEG AI Solutions | 1 day |
| Tableau-style CSV/Excel export of SQL output | Capabilities Tech Hub | 0.5 day |
| Neo4j graph: category > sub-category > product > brand | Retail CoE | 3–5 days; cut first |
| One PySpark job on Olist, with benchmark logs, no live cluster | PEG Alpha | 2–3 days |

## Datasets by week

Week 1 uses Superstore. Week 2's upload demo adds Online Retail II. Olist is only needed if the PySpark add-on is chosen. PDFs are Week 4 RAG content and are on the cut list.

## Progress

- 2026-11-08: v2 product document incorporated into `architecture.md`, `agents.md`, `decisions.md`, and this file. No week has been executed. No DDL has been applied.
- 2026-11-08: Week 1 DDL and Superstore loader written (`app/infra/schema.sql`, `app/infra/load_superstore.py`). Not applied. Local PostgreSQL 18 requires a password, and none is available to the session.
- 2026-11-08: User created empty `nexus_db`. Schema and Superstore load still blocked on the `postgres` role password.
- 2026-11-08: Applied `app/infra/schema.sql` and loaded Superstore. `sales_clean` has 9800 rows, order dates 2015-01-03 through 2018-12-30, revenue 2261536.78. Quantity, unit price, discount, cost, profit, and channel are null.
- 2026-11-08: Week 1 status corrected from "not started" to "Superstore loaded". `run_sql`, the golden set, the checker, and the CI eval script are still open.
- 2026-11-08: Week 1 complete. `run_sql`, the checker, the 25-question golden set, and `app/eval/runner.py` pass at 100% against the 85% / 98% / 90% targets. GitHub Actions remains Week 4.
- 2026-11-08: Week 2 complete. Ingestion accepts the six test files. `python app/packages/ingest/test_week2.py` passes, and the Week 1 eval still passes.
- 2026-11-08: Week 3 screen started at `app/apps/web`. The three panes render. Upload and answers are not connected.
- 2026-11-08: The v2.2 product file matches the incorporated v2 document. No second copy was added.
- 2026-11-08: Week 3 screen is connected to FastAPI. Chat streams a golden-set answer or a refusal. `runs`, `feedback`, and `eval_results` exist. Document search is still absent.
- 2026-11-08: The chat loop is an agent. It chooses `get_schema`, `run_sql`, or `read_kb`, and a later turn can see the earlier one. Groq `openai/gpt-oss-120b` is the first model. Document search is still absent.
- 2026-11-08: The screen is a chat. Health, trace, and eval are no longer a second and third column. Unused UI components were removed. No model call was made for this change.
- 2026-11-08: Chat streams a status line as each tool starts, then the answer tokens as they are written. Scripted tests cover the event order. No live model call was made for this change.
- 2026-11-08: Streamed tokens keep their spaces, so markdown renders as the answer is written. The prompt now asks for a sentence instead of a field dump such as `subcategories=17`.
- 2026-11-08: The question path is written as one file per step in `context/agent/`. No model call was made for this change.
- 2026-11-08: Fixed UI tool call display: shows one pulsating step while running, disappears with no persistence when answer begins.
- 2026-11-08: Enforced UTF-8 encoding on Windows `psql` subprocess calls in `db.py` to fix `UnicodeEncodeError` on narrow spaces and quotes.
- 2026-11-08: Made number checker context-aware (includes prompt and SQL text) and supported ordinal suffixes (`8th`, `26th`). Added clarification question support in `system.md`, `checker.py`, and `graph.py` so ambiguous filters ask the user without tripping the checker.
- 2026-11-08: Production-grade backend refactor: decomposed `graph.py` and `main.py` into dedicated modules (`state.py`, `formatting.py`, `nodes/`, `tools/`, `schemas.py`, `sse.py`, `services/`, `routers/`). All test suites pass 100%.
- 2026-11-08: Logged architectural plans for implementation:
  1. `run_python` sandboxed math execution tool, expanding `checker.py` to trace and verify Python computation output.
  2. Dynamic column ingestion via `sales_clean.attributes JSONB` payload to preserve arbitrary commercial columns while retaining strict domain-fit guardrails.
- 2026-11-09: Week 4 items completed: `run_python` sandboxed math execution tool, dynamic `attributes JSONB` preservation with `upload_attribute_schema`, per-upload analytical capabilities, and fast batch mapping. Evaluated against 30-question golden set at 100% SQL correctness, 100% numeric faithfulness, and 100% refusal accuracy.
- 2026-11-09: Senior-engineer repository reorganization and cleanup:
  1. Decoupled root into `frontend/` (Next.js 16) and `backend/` (FastAPI with entry point `backend/main.py`).
  2. Streamlined `backend/agent/`: structured the 4 core tools (`get_schema.py`, `run_sql.py`, `read_kb.py`, `run_python.py`) into dedicated modular files, and unified graph nodes and token extractors into `nodes.py`.
  3. Colocated Pydantic models directly within domain routers (`workspaces.py`, `uploads.py`, `runs.py`, `eval.py`) and inlined SSE formatting into `chat_service.py`.
  4. Consolidated all unit and integration tests into `backend/tests/` (20/20 passing).
  5. Fixed LLM Python tool indentation bug (`"That step was rejected"`) via `clean_code()` normalizer in `run_python.py` and expanded preview cap from 15 to 25 rows to eliminate category truncation and redundant queries.
  6. Implemented full chat audit trail persistence: intermediate steps, durations, statuses, queries, and outputs are persisted in PostgreSQL `runs` (`checker_result`, `python_results`) and re-hydrated when reloading rooms/threads.
