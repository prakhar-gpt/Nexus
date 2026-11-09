# Nexus Project — AI Coding Agent Guidelines

You are an expert AI engineer pair-programming on the **Nexus Retail Data Room Copilot**.

## MANDATORY SESSION START PROTOCOL
Whenever a new chat session is invoked, you MUST execute this protocol before writing code or proposing changes:

1. **Read `context/active-context.md` first**: This is the real-time project brain. It holds the active state, recent refactors, and what is currently in progress.
2. **Consult `context/INDEX.md`**: Use it to route directly to relevant documentation (`context/architecture.md`, `context/decisions.md`, `context/agent/README.md`) instead of preloading everything.
3. **Internalize the Codebase Architecture**:
   - `frontend/`: Standalone Next.js 16 app (TypeScript, Tailwind, shadcn/ui, JetBrains Mono, warm stone palette).
   - `backend/main.py`: FastAPI entry point (`uvicorn main:app --reload`).
   - `backend/db/`:
     - `changesets/`: Versioned migration scripts (`001_initial_schema.sql`, `002_ingest_tables.sql`, `003_week3_tables.sql`, `004_week4_attributes.sql`, `reader.sql`, `writer.sql`).
     - `seeds/`: Initial data loader (`load_superstore.py`).
   - `backend/api/`:
     - `routers/`: Focused FastAPI routers (`workspaces.py`, `uploads.py`, `runs.py`, `eval.py`) with colocated Pydantic models.
     - `services/`: Domain services (`chat_service.py`, `workspace_service.py`, `upload_service.py`, `eval_service.py`).
   - `backend/agent/`:
     - `nexus/`: Primary copilot agent (`graph.py`, `nodes.py`, `checker.py`, `sandbox.py`, `prompts/system.md`, `tools/` with `get_schema.py`, `run_sql.py`, `read_kb.py`, `run_python.py`).
     - `architect/`: Deterministic high-speed schema profiler and architect agent (`graph.py`, `nodes.py`, `rules.py`, `tools/`).
     - `db.py`: PostgreSQL connection management (`nexus_reader`).
     - `model.py`: LLM client instantiation.
   - `backend/ingest/`:
     - `reader.py`: File safety validation, CSV/XLSX extraction, formula sanitization, and cell parsing.
     - `mapping.py`: Canonical column mapping, RapidFuzz matching, retail synonyms, and analytical capabilities (`compute_capabilities`).
     - `store.py`: Postgres writer connection and query execution (`execute`, `get_writer_connection`, `sql_literal`).
     - `pipeline.py`: Ingestion workflow orchestration (staging, validation, quarantine, batch commit).
     - `__init__.py`: Clean package gateway.
   - `backend/eval/`:
     - `golden_set.json`: Unified single source of truth for all 30 benchmark test cases.
     - `runner.py`: Streamlined evaluation runner.
   - `backend/tests/`: Consolidated pytest suite (`conftest.py`, `test_api.py`, `test_atomicity.py`, `test_checker.py`, `test_ingest.py`, `test_loop.py`, `test_sql_guard.py`).
   - `context/`: Project memory and architectural decision logs.
   - `datasets/`: Public & synthetic datasets (`datasets/Superstore/Superstore.csv`).

## CRITICAL OPERATIONAL GUARDRAILS
- **Zero Mental Math**: The LLM must NEVER compute commercial numbers in text. All figures must originate from `run_sql` or `run_python` outputs, verified by `checker.py`.
- **Read-Only Database Security**: SQL queries execute strictly under the `nexus_reader` role with RLS (`SET LOCAL app.workspace_id = ...`), a 5s statement timeout, 25-row preview cap, and 200-row fetch limit.
- **Python Tool Robustness**: Code passed to `run_python` is normalized with `clean_code()` to eliminate leading indentation errors and code fences before AST checking, running in an isolated OS subprocess (no network, 10s timeout, 256MB cap).
- **Audit Trail Persistence**: Every chat turn preserves the full execution audit trail (tool calls, durations, statuses, queries, outputs) in PostgreSQL `runs` and hydrates on workspace reload.

## OPERATIONAL PROTOCOL & STANDING EXECUTION RULES
**Standing Rule — Do NOT run tests, typecheck, lint, build commands, or the eval runner unless explicitly requested by the user.**
This applies to all tasks, including UI-only changes, and overrides any previous "run tests after each stage" or "run typecheck, lint, and tests" instructions in earlier prompts, plans, or docs.

1. **No Autonomous Test or Build Execution**: Do NOT run `pytest`, the backend suite, `backend/eval/runner.py`, `npm run typecheck`, `lint`, frontend tests, build commands, or manual-checklist walkthroughs on your own.
2. **No Autonomous Server or Browser Launch**: Do not start dev servers, take screenshots, or open a browser to verify unless explicitly asked.
3. **Execution Scope**: Write the code, then stop. Keep reports concise: files added, files changed, dead code, assumptions, anything unfinished.
4. **Writing Tests Allowed**: You may still WRITE or UPDATE test files when the task calls for them. Just do not execute them.
5. **Report Ending Requirement**: End every report with one line listing what the user should run to verify, e.g.: "To verify: `pytest backend/tests`, `npm run typecheck --prefix frontend`." Do not run them.
6. **Risk Flagging**: If you believe something is likely broken (a changed signature, a migration that could fail, an unresolved type), state it in the report in one line. Do not run commands to confirm it.
7. **Static Reads Permitted**: Opening files, searching code, and reading logs pasted by the user are fully permitted. Running commands that execute project code or modify state (tests, migrations, scripts, servers) requires explicit user instruction.
8. **Explicit Command Invocations**: When the user says "run the tests" (or names a command), run exactly that and report the result. The permission applies to that specific request only and is not standing.
9. **No Autonomous Commits**: Commit after a stage only if the user explicitly asked to commit. Otherwise leave changes uncommitted.

