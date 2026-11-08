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
     - `tools/`: Exactly 4 modular tools (`get_schema.py`, `run_sql.py`, `read_kb.py`, `run_python.py`), aggregated in `__init__.py`.
     - `nodes.py`: LangGraph nodes (`agent_node`, `tools_node`, `checker_node`, `route_next_step`) and token extractors.
     - `graph.py`: LangGraph state machine, checkpointing (`MemorySaver`), and streaming generator (`stream`).
     - `checker.py`: Deterministic claim-to-evidence number verifier.
     - `sandbox.py`: Isolated subprocess execution boundary for Python code.
     - `db.py`: PostgreSQL connection management (`nexus_reader`).
     - `prompts/system.md`: Hardened system prompt with explicit SQL-then-Python directives.
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

## VERIFICATION PROTOCOL
Before completing any task, always run and verify:
1. `pytest backend/tests` (Must pass 20/20).
2. `python backend/eval/runner.py` (Must pass 100% sql correctness, 100% numeric faithfulness, 100% refusal accuracy).
3. If frontend files were modified: `npm.cmd run typecheck --prefix frontend` (0 errors).
4. Update `context/active-context.md` and append any architectural decision to `context/decisions.md`.
