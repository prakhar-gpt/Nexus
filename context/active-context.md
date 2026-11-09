Created At: 2026-11-09T00:35:50+05:30
Updated At: 2026-11-09T05:47:00+05:30

Nexus is organized with a clean, senior-engineer root layout:
- `frontend/`: Standalone Next.js 16 app (TypeScript, Tailwind, shadcn/ui, JetBrains Mono, warm stone palette). Completely in-chat dataset upload and schema review.
- `backend/`: Pure Python FastAPI service with entry point `backend/main.py` (`uvicorn main:app --reload` from `backend/` or `uvicorn backend.main:app` from root).
- `context/`: Project documentation and architecture decisions.
- `datasets/`: Public & synthetic datasets (`datasets/Superstore/Superstore.csv`).

### Current Active State & Refactors Completed
- **Elimination of Hash Dataset Labels (Original File Name Fidelity)**:
  - Fixed root cause where `_init_schema_proposal` previously inspected `path.stem` from the disk storage cache (which saves uploaded files by sha256 digest e.g. `dbb0f167b27ccf02.csv`), converting it to title-cased hashes like `Dbb0F167B27Ccf02`.
  - Replaced disk path stems with `original_name` from the `uploads` table across `_init_schema_proposal`, `approve_upload_schema`, and `create_and_load_custom_table` (e.g. `Superstore.csv` -> `Superstore`).
  - Added hex-hash and internal table name detectors (`/^[0-9a-fA-F]{12,}$/` and `ds_*`) on both backend and frontend (`chat-store.tsx` and `schema-architect-card.tsx`), guaranteeing that handoff messages and suggested questions strictly display the friendly file name.
  - Migrated existing records in `datasets` table to title-cased `original_name`.
- **UI Distraction Cleanup (No Red Tool Dots)**:
  - Removed decorative red pulsing dots (`bg-primary`) from `frontend/components/tool-line.tsx` and `frontend/components/agent-steps.tsx`.
  - Active tool execution pulses gently via typography (`animate-pulse font-medium text-foreground/80 font-mono text-[12px]`) without alarming red dots.
- **Modern In-Chat Schema Approval & UI Polish (Decision 50)**:
  - **Shadcn Component Integration**: Replaced unstyled native `<select>` dropdowns for column `Type` and `Role` with shadcn `DropdownMenu` components with check indicators. Replaced raw tables with shadcn `Table` (`TableHeader`, `TableBody`, `TableRow`, `TableHead`, `TableCell`), `ScrollArea`, and `Badge`.
  - **Frictionless Scrolling**: Fixed height inheritance in `ScrollArea` (`h-[280px]` with `containerClassName="contents"` on `Table`) to enable smooth vertical and horizontal scrolling with pinned sticky headers (`sticky top-0 z-10 bg-muted`), eliminating conflicting nested `overflow-x-auto` wrappers.
  - **Global Hairline Scrollbars**: Added global calm scrollbar styling in `frontend/app/globals.css` with WebKit scrollbars (6px width, `--border` track/thumb, `--radius: 0`) and Firefox `scrollbar-width: thin; scrollbar-color: var(--border) transparent` adhering strictly to `design-language.md`.
  - **Markdown-Rendered Table Grain**: Sanitized LLM-generated raw prefix artifacts (`Grain:**`, `**Grain:**`, `One row represents:`) on both backend (`graph.py`) and frontend (`cleanGrainText`) via regex. Rendered grain with `ReactMarkdown` and `remarkGfm`, styling backtick identifiers (e.g. `` `order_id` ``, `` `product_id` ``) as hairline monospace code badges, with inline click-to-edit support and debounced server synchronization.
  - **Single-Tool Pulsating Streaming (`AgentSteps`)**: Replaced the stacked step list with loud green checkmarks with the exact single-line pulsating tool pattern used by Nexus `ToolLine`. While profiling or loading, exactly ONE quiet tool label pulses at a time (`animate-ping` + `animate-pulse`), eliminating visual noise. Completed steps collapse into a calm, unbadged disclosure.
  - **Immediate Table Approval & COPY Load**: Fixed "Approve & create table" to transition immediately via local state (`setLocalStatus("loaded")`), creating the `user_data.ds_*` table and streaming rows via PostgreSQL COPY in ~500ms without UI latency.
  - **Friendly Dataset Labeling & Commercial Question Suggestions**: Replaced raw internal relation names (e.g. `ds_776`) with friendly dataset labels (e.g. `Superstore`). Re-classified non-measures in `backend/agent/architect/nodes.py` (columns with `code`, `zip`, `postal`, `phone`, `id`, `nbr` are classified as `identifier` or `dimension`, never as `measure`). Implemented retail-prioritized question suggestions (`_generate_suggested_questions`) prioritizing commercial metrics (`revenue`, `sales`, `profit`, `quantity`) and core retail dimensions (`category`, `segment`, `region`), generating defensible commercial due diligence inquiries instead of mathematical aggregations on postal codes.
- **`sales_clean` Deprecation (Decision 49)**:
  - `sales_clean` is formally deprecated via PostgreSQL database comments and system prompt directives.
  - All new tabular datasets (.csv, .xlsx) are ingested exclusively as custom datasets (`user_data.ds_*`), cataloged in `datasets` and `dataset_columns`, isolated by workspace RLS (`nexus_reader`).
  - `sales_clean` remains strictly as a read-only historical benchmark fixture to support the 30-question evaluation suite (`backend/eval/golden_set.json`).
- **Database Table Unification**:
  - Dropped redundant tables `upload_events` and `architect_runs`.
  - All agent events (safety, parse, profiling, proposal, and chat) use the single unified `agent_events` ledger (`id`, `workspace_id`, `agent_kind`, `run_id`, `upload_id`, `seq`, `stage`, `event_type`, `label`, `payload`, `created_at`).
  - All execution audit trails are stored in the shared `runs` table (with `agent_kind` and `upload_id` columns).
- **Single Agent Persona ("Nexus")**:
  - Unified agent identity across both frontend and backend. UI labels replaced: "Schema Architect" and "Schema Agent" are removed in favor of "Nexus" as a cohesive copilot.
  - Removed "Active" badge from left sidebar.
- **Blazing Fast In-Chat Profiling (< 1.0 Second)**:
  - Eliminated the slow 20-roundtrip LLM tool loop.
  - In `backend/agent/architect/graph.py`, profiling samples up to 500 rows and executes deterministic type inference, date format detection, null rate calculation, and snake_case mapping in <100ms.
  - Streams immediate human-readable progress steps ("Read file structure", "Profiled column data types and null rates", "Determined table grain") to `agent_events` and emits the proposal card within ~1 second.
- **Dead & Unused Code Purge**:
  - Deleted legacy modal stepper and dead mapping components: `pipeline-stepper.tsx`, `mapping-table.tsx`, `schema-review-table.tsx`, `dropzone.tsx`, `sidebar/ingestion-section.tsx`, and `sidebar/workspace-selector.tsx`.
  - Cleaned up unused mapping confirmation functions, states, and endpoints from `frontend/components/dashboard.tsx` and `backend/api/services/upload_service.py`.

### Verification Suite Results
- **Pytest Suite (`pytest backend/tests`)**: 30/30 passed (100%).
- **Frontend Typecheck (`npm run typecheck --prefix frontend`)**: 0 errors.
- **End-to-End Flow Verification**: Passed across all stages:
  1. Workspace creation
  2. Superstore CSV upload
  3. `agent_events` real-time step streaming (single tool pulsating at a time)
  4. Instant schema proposal generation with markdown-rendered grain
  5. One-click schema approval & PostgreSQL streaming COPY (9,800 rows loaded in ~500ms)
  6. Human-friendly dataset labeling (`Superstore`) and retail-intelligent question chips
  7. `get_schema` discovery of custom table `ds_*`
  8. Read-only SQL execution under RLS
  9. Live Nexus query answering with AST guard and deterministic `checker` verification.
- **Golden Set Benchmark (`backend/eval/runner.py`)**: 100% SQL correctness, 100% numeric faithfulness, 100% refusal accuracy.
