Created At: 2026-11-09T00:35:50+05:30
Updated At: 2026-11-09T01:20:00+05:30

Nexus is organized with a clean, senior-engineer root layout:
- `frontend/`: Standalone Next.js 16 app (TypeScript, Tailwind, shadcn/ui, JetBrains Mono, warm stone palette).
- `backend/`: Pure Python FastAPI service with entry point `backend/main.py` (`uvicorn main:app --reload` from `backend/` or `uvicorn backend.main:app` from root).
- `context/`: Project documentation and architecture decisions.
- `datasets/`: Public & synthetic datasets (`datasets/Superstore/Superstore.csv`).

### Backend Architecture
- **Entry Point**: `backend/main.py` sets up CORS, mounts routers, and defines root health checks.
- **Database (`backend/db/`)**:
  - `changesets/`: Versioned migration scripts (`001_initial_schema.sql`, `002_ingest_tables.sql`, `003_week3_tables.sql`, `004_week4_attributes.sql`, `reader.sql`, `writer.sql`).
  - `seeds/`: Initial seed data loader (`load_superstore.py`).
- **API Domain Routers & Services (`backend/api/`)**:
  - `routers/` (`workspaces.py`, `uploads.py`, `runs.py`, `eval.py`): Clean HTTP endpoints with Pydantic schemas colocated directly within their domain routers.
  - `services/` (`chat_service.py`, `workspace_service.py`, `upload_service.py`, `eval_service.py`): Business logic. SSE formatting is inlined cleanly into `chat_service.py`.
- **Agent Architecture (`backend/agent/`)**:
  - `tools/`: Exactly the 4 core tools cleanly modularized into dedicated files:
    - `get_schema.py`: Inspects table schemas, unmapped JSONB attributes, and analytical capabilities.
    - `run_sql.py`: AST-guarded, read-only SQL under RLS (`nexus_reader`), with `max_preview = 25` rows.
    - `read_kb.py`: Safe reference markdown reader under `backend/kb/`.
    - `run_python.py`: Sandboxed Python calculation runner with AST checks and `clean_code()` normalizer to prevent indentation errors from LLM code fences.
    - `__init__.py`: Exports `TOOLS = [get_schema, run_sql_tool, read_kb, run_python]` and execution dispatches.
  - `nodes.py`: Consolidated LangGraph loop nodes (`agent_node`, `tools_node`, `checker_node`, `route_next_step`) and visible token extractors (`extract_visible_chunk`, `extract_text_delta`).
  - `graph.py`: LangGraph state machine, thread-level checkpointing (`MemorySaver`), and streaming generator (`stream`).
  - `checker.py`: Deterministic numerical verification comparing draft claims against SQL rows, user messages, and Python execution results.
  - `sandbox.py`: Subprocess execution boundary (no network, 10s timeout, 256MB cap).
  - `db.py`: PostgreSQL reader/writer connections (`READER_SQL` in `backend/db/changesets/reader.sql`).
  - `model.py`: LLM provider resolver (Groq, OpenRouter, DeepSeek).
  - `prompts/system.md`: Hardened system prompt with explicit directives to execute SQL before calling `run_python`.
- **Ingestion (`backend/ingest/`)**:
  - `reader.py`: File safety validation, CSV/XLSX extraction, formula sanitization, and type cleaning.
  - `mapping.py`: Canonical column mapping, RapidFuzz matching, retail synonyms, and analytical capabilities (`compute_capabilities`).
  - `store.py`: Postgres writer connection and query execution gateway (`execute`, `get_writer_connection`, `sql_literal`).
  - `pipeline.py`: Ingestion workflow orchestration (staging, validation, quarantine, COPY commit).
  - `__init__.py`: Package gateway cleanly re-exporting public ingestion interfaces.
- **Evaluation (`backend/eval/`)**:
  - `golden_set.json`: Unified single source of truth containing all 30 questions (`sql`, `code`, `missing`, `fixture`) and ground-truth expected outputs.
  - `runner.py`: Streamlined evaluation runner scoring SQL correctness, numeric faithfulness, and refusal accuracy without redundant external question dicts.
- **Consolidated Tests (`backend/tests/`)**:
  - All test suites consolidated into `backend/tests/` (`conftest.py`, `test_api.py`, `test_atomicity.py`, `test_checker.py`, `test_ingest.py`, `test_loop.py`, `test_sql_guard.py`).

### Verification & Performance
- **Golden Set Benchmark (`backend/eval/runner.py`)**: 100% SQL correctness, 100% numeric faithfulness, 100% refusal accuracy across all 30 questions.
- **Pytest Suite (`pytest backend/tests`)**: 20/20 passed (100%).
- **Multi-Step & Python Tool Stability**:
  - Eliminated `"That step was rejected"` bugs caused by LLM leading spaces / code fences via `clean_code()` in `backend/agent/tools/run_python.py`.
  - Preview size increased from 15 to 25 rows in `run_sql.py` to prevent category truncation (e.g. Fasteners at #17) and multi-query token bloat.
  - Increased `MAX_TOOL_STEPS` to 8 in `backend/agent/state.py`.
- **Full Chat Audit Trail Persistence & Multi-Tool Execution**:
  - `save_run` in `backend/api/services/chat_service.py` stores intermediate tool calls (`steps`), inputs, outputs, durations, statuses, queries, and results into `runs.checker_result` and `runs.python_results`.
  - `get_workspace_turns` in `backend/api/services/workspace_service.py` re-hydrates full tool steps upon room/thread reload.
  - "Show tool execution" disclosure in `frontend/components/audit-bar.tsx` and `frontend/components/query-panel.tsx` renders every tool call made (input, output, syntax-highlighted code, SQL preview table, and chart) with copy controls.

### Unresolved / Planned for Implementation
- **CI & Deployment**: GitHub Actions workflow for `python backend/eval/runner.py` and `pytest backend/tests` regression checks on push; Docker Compose packaging.
- **Knowledge Base / Document Q&A (`search_docs`)**: pgvector semantic retrieval over PDF diligence memos.
- Superstore extract note: Nulls for `quantity`, `unit_price`, `discount_pct`, `cost`, `profit`, and `channel` are expected; the agent refuses queries on these missing dimensions while deterministic checking verifies the refusal.
