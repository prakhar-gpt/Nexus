# Nexus Workspace Rules & Guidelines

You are an expert AI engineer pair-programming on the **Nexus Retail Data Room Copilot**.

## SESSION INITIALIZATION DIRECTIVE
Whenever a new chat session begins or you receive a new user request:
1. **Always read `context/active-context.md` FIRST**: It contains the real-time project state, completed architecture, and what is currently in progress.
2. **Consult `context/INDEX.md`**: Route directly to the specific context files needed (`architecture.md`, `decisions.md`, `agent/README.md`) instead of preloading everything.
3. **Know the Architecture**:
   - `frontend/`: Next.js 16 app (TypeScript, Tailwind, shadcn/ui, JetBrains Mono, warm stone palette).
   - `backend/main.py`: FastAPI entry point (`uvicorn main:app --reload`).
   - `backend/db/`:
     - `changesets/`: Versioned migration scripts (`001_initial_schema.sql`, `002_ingest_tables.sql`, `003_week3_tables.sql`, `004_week4_attributes.sql`, `reader.sql`, `writer.sql`).
     - `seeds/`: Initial data loader (`load_superstore.py`).
   - `backend/api/`: Domain routers (`workspaces.py`, `uploads.py`, `runs.py`, `eval.py`) with colocated Pydantic models, and domain services.
   - `backend/agent/`: Exactly 4 modular tools in `tools/` (`get_schema.py`, `run_sql.py`, `read_kb.py`, `run_python.py`), LangGraph state machine in `graph.py`, nodes in `nodes.py`, claim verification in `checker.py`, and subprocess execution in `sandbox.py`.
   - `backend/ingest/`: 4 cohesive modules (`reader.py`, `mapping.py`, `store.py`, `pipeline.py`).
   - `backend/eval/`: Single-source `golden_set.json` (all 30 questions + ground truth) and `runner.py`.
   - `backend/tests/`: Consolidated pytest suite (`pytest backend/tests`).
   - `context/`: Project memory and architectural decision logs.

## CORE PRINCIPLES
- **No Mental Arithmetic**: Every commercial number must come from `run_sql` or `run_python` outputs verified by `checker.py`.
- **Database Isolation**: Queries are SELECT-only under non-superuser `nexus_reader` with RLS (`app.workspace_id`), 5s timeout, and 25-row preview cap.
- **Python Sandbox**: Code executed via `run_python` is pre-normalized via `clean_code()` to strip code fences and flatten whitespace, then run in a networkless, memory-capped subprocess.
- **Verification Mandatory**: Always run `pytest backend/tests` and `python backend/eval/runner.py` before completing turns.
