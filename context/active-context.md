Created At: 2026-11-09T00:35:50+05:30
Updated At: 2026-11-09T06:20:00+05:30

### Standing Operational Rule: Autonomous Test & Build Execution Prohibited
- **Zero Autonomous Test/Build/Server Execution**: Do NOT run `pytest`, `backend/eval/runner.py`, `npm run typecheck`, `lint`, frontend tests, build commands, or manual checklist walkthroughs unless explicitly instructed by the user. Do not start dev servers, take screenshots, or open browsers.
- **Reporting Protocol**: Write code, stop, and keep the report concise (files added, files changed, dead code, assumptions, unfinished items). Flag suspected breakages in one line without running commands. End every report with one line specifying the exact commands for the user to verify (e.g. `To verify: pytest backend/tests, npm run typecheck --prefix frontend`).
- **Tests Allowed to be Written**: Creating or updating test files is permitted; executing them is strictly prohibited unless asked.
- **Explicit Instruction Only**: Permission to run any test/build/script applies strictly to the single request where granted and is never standing. Commit only when requested.

Nexus is organized with a clean, senior-engineer root layout:
- `frontend/`: Standalone Next.js 16 app (TypeScript, Tailwind, shadcn/ui, JetBrains Mono, warm stone palette).
- `backend/`: Pure Python FastAPI service with entry point `backend/main.py` (`uvicorn main:app --reload` from `backend/` or `uvicorn backend.main:app` from root).
- `context/`: Project documentation and architecture decisions.
- `datasets/`: Public & synthetic datasets (`datasets/Superstore/Superstore.csv`).

### Current Active State & Refactors Completed

#### 1. Data Rooms Hub Shell Unification (Decision 54)
- **Unified App Shell**: Redesigned the Data Rooms Hub (`WorkspacesView`) to use the exact same shell as the room view: a 260px left sidebar and a main pane in the shared 720px column. Eliminated the separate 56px top header bar, 960px container, and card grid.
- **Shared Sidebar Component (`Sidebar`)**: Added `"hub"` and `"room"` content modes to the single sidebar component. In hub mode, renders the Nexus wordmark, the "+ New data room" button (primary red when rooms exist, quiet outline when zero rooms exist), `RoomList` with dataset counts, activity dates, hover-reveal delete confirmation, and grouping when > 8 rooms, plus `UserProfileFooter`.
- **Main Pane Welcome & Empty State**: Left-aligned in the 720px column, rendering `"Welcome, {first name}"` (or `"Welcome"`), followed by `"Select a data room to continue, or create a new one."` when rooms exist, or the dashed-hairline empty panel with the primary New data room button when zero rooms exist.
- **Typography**: Playfair Display configured for all headers (`h1`–`h6`, `--font-heading`) via `next/font/google` and `@layer base` in `globals.css`; JetBrains Mono remains body/code font.
- **Documentation**: Updated `context/design-language.md` (Screen 1 Hub spec, removal of 960px rule, canonical strings) and added Decision 54 to `context/decisions.md`.

#### 2. Datasets Belong to Data Room, Not a Chat (Decisions 52 & 53)
- **Elimination of Refresh Split & Ghost Run Purge**:
  - Removed `INSERT INTO runs ... ('Schema Analysis')` from `backend/api/services/upload_service.py`. Upload and profiling states now persist exclusively in `uploads`, `agent_events`, and `datasets`.
  - Migration [`backend/db/changesets/007_chats_and_datasets.sql`](file:///c:/Users/praxc/OneDrive/Desktop/Projects/Nexus/backend/db/changesets/007_chats_and_datasets.sql) executed and applied:
    - Purged all 24 ghost "Schema Analysis" runs from `runs` (genuine Q&A turns preserved).
    - Normalized legacy NULL `thread_id` records to `'default'`.
    - Created dedicated table `threads (id text, workspace_id bigint, title text, selected_dataset_ids bigint[], created_at, updated_at, PRIMARY KEY (workspace_id, id))`.
    - Configured Row-Level Security: `threads_reader_workspace` for `nexus_reader` (using `app.workspace_id`), and `threads_writer_all` for `nexus_writer`.
    - Backfilled genuine threads from existing valid runs.
  - Added defensive guards in `get_turns()` (`workspace_service.py`) to skip any proposal-shaped JSON.
- **Server-Side Per-Chat Dataset Selection & Security**:
  - `backend/api/services/workspace_service.py`:
    - `list_threads(workspace_id)`: reads from `threads`.
    - `get_or_create_thread(workspace_id, thread_id)`: creates thread initialized with all active datasets in the workspace on first interaction.
    - `update_thread_datasets(workspace_id, thread_id, dataset_ids)`: strictly validates dataset IDs against `workspace_id`.
    - `list_workspace_datasets(workspace_id)`: returns active datasets with row counts, quarantine counts, and table grains.
    - `remove_dataset(workspace_id, dataset_id)`: atomic transaction dropping `user_data.ds_*`, deleting catalog & quarantine entries, and executing `array_remove(selected_dataset_ids, dataset_id)` across all threads in the workspace.
  - `backend/api/routers/workspaces.py`:
    - Endpoints added: `GET /workspaces/{id}/datasets`, `DELETE /workspaces/{id}/datasets/{dataset_id}`, and `PATCH /workspaces/{id}/threads/{thread_id}/datasets`.
    - In `POST /workspaces/{id}/chat`: strictly resolves `allowed_dataset_ids` from `threads` in PostgreSQL, ignoring client-sent lists. Rejects requests with `HTTP 400 ("Select a dataset to ask about")` when custom datasets exist but none are checked.
  - **Tool & Engine Filtering**:
    - `backend/agent/nexus/tools/get_schema.py`: filters custom datasets by `allowed_dataset_ids`.
    - `backend/agent/nexus/tools/run_sql.py`: AST guard inspects SQL queries against all workspace datasets. If a query targets an unselected dataset, it rejects execution with `SqlRejected("That dataset is not enabled for this chat")`.
    - LangGraph State (`graph.py`, `nodes.py`, `state.py`): `allowed_dataset_ids` passes through state and config, completely inaccessible to LLM manipulation.
  - **Prompt Directives (`backend/agent/nexus/prompts/system.md`)**: Instructs Nexus that when multiple datasets are enabled, it selects tables by grain and description and explicitly names the source dataset in answers.
- **Frontend Architecture & Components**:
  - Created `frontend/components/ui/checkbox.tsx` with `@base-ui/react/checkbox`.
  - Created `frontend/components/sidebar/dataset-section.tsx` featuring per-chat checkboxes, row counts, grain lines, and overflow actions (rename, download quarantine, delete dataset dialog).
  - Updated `frontend/lib/api.ts` with `Dataset` interface and extended `Room` and `Thread` types.
  - Integrated `DatasetSection` into `frontend/components/sidebar/index.tsx`.
- **Backend Test Suite & Golden Set Alignment**:
  - Created `backend/tests/test_threads_and_datasets.py` covering multi-tenant isolation, dataset filtering, unselected table rejection, empty selection handling, and atomic cascades.
  - Evaluation runner defaults `allowed_dataset_ids = None` to include all workspace datasets and `sales_clean`, ensuring 100% benchmark fidelity (30/30 golden set).

#### 2. Prior Refactors Preserved & Active
- **Full Database Clean Slate**: `user_data` schema isolated; base tables RLS enabled.
- **Original File Name Fidelity**: Disk storage hashes eliminated from UI/agent labels in favor of `original_name` (e.g. `Superstore`).
- **UI Distraction Cleanup**: Red pulsing dots removed; clean single-tool typography streaming in `agent-steps.tsx`.
- **Fast In-Chat Schema Profiling (<1s)**: Deterministic typing and date detection sampling 500 rows.
- **`sales_clean` Deprecated (Decision 49)**: Benchmark fixture only; all user data routes to `user_data.ds_*`.
- **Design Language Modernization (Decision 51)**: Left edge alignment, single primary action, dashed empty states, plain English copy.

### Verification Suite Baseline
- **Pytest Suite (`pytest backend/tests`)**: 36/36 passed (100%).
- **Golden Set Benchmark (`python backend/eval/runner.py`)**: 100% SQL correctness, 100% numeric faithfulness, 100% refusal accuracy.
- **Frontend Typecheck (`npm run typecheck --prefix frontend`)**: 0 errors.

### In Progress / Next Immediate Steps
1. **Frontend Layout & Dashboard Wiring**:
   - In `frontend/app/(app)/rooms/[roomId]/layout.tsx` and `dashboard.tsx`:
     - Wire `datasets` from room into `Sidebar`.
     - Wire active thread `selectedDatasetIds` to `Sidebar`'s `DatasetSection`.
     - Handle `onToggleDataset` calling `PATCH /workspaces/{roomId}/threads/{activeThreadId}/datasets` with optimistic updates.
     - Handle `onRemoveDataset` calling `DELETE /workspaces/{roomId}/datasets/{datasetId}`.
2. **Move Setup Card Out of Chat Timeline**:
   - In `frontend/components/chat-pane.tsx` and `dashboard.tsx`:
     - Remove upload state from chat message flow.
     - Render `SchemaArchitectCard` as a room-level setup card above composer / replacing empty state when an upload is in progress or in `needs_schema_review`.
     - Once approved, collapse setup card into the sidebar dataset list.
3. **Composer Locking & Dynamic Question Chips**:
   - Disable composer if 0 datasets exist ("Add a dataset to start") or if 0 datasets are checked ("Select a dataset to ask about").
   - Derive suggested question chips strictly from the checked datasets.
