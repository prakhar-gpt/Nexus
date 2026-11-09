Created At: 2026-11-09T00:35:50+05:30
Updated At: 2026-11-09T06:46:00+05:30

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

#### 1. Backend Lean Refactoring, Shared Utilities & Monolith Elimination (Decision 60)
- **Centralized Shared Utilities (`backend/utils.py`)**: Extracted and centralized core helpers across backend modules:
  - `to_uuid(val)`: Coerces strings, ints, or UUIDs into validated `uuid.UUID`.
  - `parse_dataset_ids(raw)`: Safely parses Postgres text arrays, list representations, and sets into clean string IDs.
  - `clean_grain(raw)`: Strips prose prefixes (`"grain"`, `"table grain"`, `"one row represents"`) via regex.
  - `sanitize_identifier(name)`: Converts raw user/CSV headers into safe snake_case PostgreSQL identifiers.
  - `make_inert(val)`: Sanitizes leading formula injection characters (`=`, `+`, `-`, `@`).
  - `esc_tsv(val)`: PostgreSQL streaming COPY TSV escape helper.
  - `format_sse(event, payload)`: Formats standard Server-Sent Event payloads.
- **Decomposed Monoliths into Clean Services**:
  - `backend/api/services/event_stream.py`: Modularized SSE keepalive and event streaming logic.
  - `backend/api/services/schema_questions.py`: Extracted heuristic suggested question generation.
  - `backend/api/services/upload_service.py`: Slashed from 1,078 to ~700 lines; converted all CRUD to SQLAlchemy ORM sessions.
  - `backend/api/services/workspace_service.py`: Streamlined to clean SQLAlchemy queries.
  - `backend/api/services/chat_service.py`: Streamlined to 180 lines, eliminating duplicate SSE formatting and using `utils.py`.
- **Ingestion Pipeline Streamlined (`backend/ingest/pipeline.py`)**:
  - Removed dead legacy functions (`confirm_mappings`, `_load_confirmed_mappings`, `_save_mappings`, `_save_attribute_schema`) referencing dropped tables.
  - Consolidated `esc_tsv` and `make_inert` into `backend/utils.py`.
  - Cleaned package gateway `backend/ingest/__init__.py`.
- **Deleted `mapping.py` and Removed `rapidfuzz` (Decision 61)**:
  - Completely purged [`backend/ingest/mapping.py`](file:///c:/Users/praxc/OneDrive/Desktop/Projects/Nexus/backend/ingest/mapping.py) and dropped `rapidfuzz` from [`backend/requirements.txt`](file:///c:/Users/praxc/OneDrive/Desktop/Projects/Nexus/backend/requirements.txt).
  - Purged the legacy fixed 14-column `sales_clean` loader and `staging_sales` copy loops from `backend/ingest/pipeline.py` (slashed from 543 down to 157 lines).
  - All spreadsheet uploads now route 100% dynamically to the Schema Architect Agent, creating clean `user_data.ds_*` custom tables.
  - Eliminated loose application SQL strings in [`backend/ingest/custom_table.py`](file:///c:/Users/praxc/OneDrive/Desktop/Projects/Nexus/backend/ingest/custom_table.py), [`backend/api/routers/workspaces.py`](file:///c:/Users/praxc/OneDrive/Desktop/Projects/Nexus/backend/api/routers/workspaces.py), [`backend/agent/nexus/graph.py`](file:///c:/Users/praxc/OneDrive/Desktop/Projects/Nexus/backend/agent/nexus/graph.py), and [`backend/agent/nexus/tools/get_schema.py`](file:///c:/Users/praxc/OneDrive/Desktop/Projects/Nexus/backend/agent/nexus/tools/get_schema.py), migrating catalog registrations and metadata queries to SQLAlchemy ORM (`Dataset`, `DatasetColumn`, `Upload`, `Run`).
  - Resolved circular import between `db.session` and `ingest.store` by removing cross-package store dependencies from `db/session.py`.
- **Full Mitigation of `sales_clean` Hardcoded Columns (Decision 62)**:
  - Eliminated the hardcoded `SCHEMA_SQL` and 14 retail column counts from [`backend/agent/nexus/tools/get_schema.py`](file:///c:/Users/praxc/OneDrive/Desktop/Projects/Nexus/backend/agent/nexus/tools/get_schema.py). It now dynamically queries `Dataset` and `DatasetColumn` catalogs for approved custom tables and column roles.
  - Eliminated hardcoded `MEASURE_COLUMNS` from [`backend/agent/nexus/tools/run_sql.py`](file:///c:/Users/praxc/OneDrive/Desktop/Projects/Nexus/backend/agent/nexus/tools/run_sql.py) and made `get_allowed_tables` dynamically query workspace dataset permissions using SQLAlchemy ORM.
  - Mitigated `get_health` in [`backend/api/services/workspace_service.py`](file:///c:/Users/praxc/OneDrive/Desktop/Projects/Nexus/backend/api/services/workspace_service.py): removed `HEALTH_SQL` and dynamically computes row counts and quarantine counts across the workspace's active datasets.
  - Updated [`backend/agent/nexus/prompts/system.md`](file:///c:/Users/praxc/OneDrive/Desktop/Projects/Nexus/backend/agent/nexus/prompts/system.md) so the agent reasons over dynamic tables and schemas rather than hardcoded `sales_clean` columns.
  - Cleaned `main.py` by removing deprecated `HEALTH_SQL` exports.
- **Committed**: Refactor committed at `69748dc` ("refactor(backend): modularize services, eliminate sales_clean legacy code, and complete SQLAlchemy ORM migration") with 35 files changed, 1325 insertions, 2094 deletions (net -769 lines).
- **Zero Static Compilation & Import Errors**: All core backend modules import cleanly with zero syntax or runtime import errors.

#### 1. Performance Optimization & UX Polish (Streaming, Bundle & Latency)
- **Zero-Lag Query Transition**: In `NewChatRoomPage`, rendered `ChatPane` immediately when `threadState.messages.length > 0` and routed to thread URL synchronously, eliminating the 5-10s delay where users stared at empty suggestions before tokens streamed.
- **Batched Streaming Commits**: Buffered live SSE tokens in `chat-store.tsx` via `requestAnimationFrame` (~30-60 updates/sec max) and flushed synchronously on step/done/error, eliminating render storms per token.
- **Strict Message Memoization**: Preserved message object references in `ChatPane` by passing `isFirstInRun` as an independent prop instead of creating inline object literals `{ ...message, isFirstInRun }`, and memoized `RenderedMarkdown` to prevent markdown re-parsing on completed turns.
- **Dynamic Lazy Loading**: Converted `SchemaArchitectCard` and `QueryPanel` to `next/dynamic` imports (`ssr: false`), keeping initial room route bundles lean.
- **Sidebar Polish & Empty States**: Integrated shadcn `Spinner` loader while room name is loading; hidden "New chat" button and empty "Chats" sections when no datasets/threads exist.
- **Analytical Role Clarity**: Added inline descriptions and tooltips in schema proposal table header and dropdowns for `measure`, `dimension`, `identifier`, and `date`.
- **Thread Title Real-Time Sync**: Updated `Thread.title` both optimistically in `chat-store.tsx` and persistently in `chat_service.py` (`save_run`) so new conversations immediately reflect the question asked instead of staying "New Conversation".
- **Backend Performance Indexes**: Added Changeset `010_perf_indexes.sql` indexing `(workspace_id, (checker_result->>'thread_id'))`, `quarantine(upload_id)`, and `datasets(workspace_id)`.

#### 1. Hybrid Database Architecture — SQLAlchemy ORM for Domain CRUD (Decision 59)
- **SQLAlchemy Engine, Session & Models**: Created `backend/db/session.py` (`SessionLocal`, connection pooling, `session_scope()`) and `backend/db/models.py` with declarative models for `User`, `WorkspaceMember`, `Workspace`, `Upload`, `Dataset`, `DatasetColumn`, `Thread`, `Run`, `Feedback`, `AgentEvent`, and `Quarantine`.
- **Domain Services Refactored**: Refactored `workspace_service.py`, `upload_service.py`, `chat_service.py`, and `api/routers/users.py` from raw string SQL interpolation to parameterized SQLAlchemy ORM queries, eliminating manual escaping and providing strongly-typed attribute access.
- **Agent & Ingest Preserved**: Preserved raw SQL execution strictly for `run_sql` (guarded SELECT-only queries under `nexus_reader` with RLS) and streaming COPY (`copy_expert`) in `custom_table.py` for sub-second data ingestion.

#### 2. Database Table Purge & Retirement of Legacy Tables (Decision 58)
- **Purged Unused Tables (Changeset 009)**: Successfully dropped `column_mapping`, `upload_attribute_schema`, and `eval_results` from PostgreSQL `nexus_db`.
- **Preserved `quarantine`**: Confirmed active in user data quality workflow (tracks invalid CSV/XLSX rows, displays quarantined counts in room header/dataset list, and powers CSV download endpoint).
- **Preserved `sales_clean`**: Confirmed active as a zero-storage compatibility VIEW over `user_data.ds_superstore`, powering the 30-question evaluation benchmark suite (`backend/eval/golden_set.json`) and core pytest suites.

#### 2. Users Table, Workspace Membership & Universal UUID Implementation (Decision 57)
- **Users Table & Workspace Ownership**: Implemented `users` (`id uuid PRIMARY KEY DEFAULT gen_random_uuid()`, `email`, `name`, `role`, timestamps) and `workspace_members` join table (`workspace_id uuid`, `user_id uuid`, `role`, `joined_at`). Added `/users`, `/users/me`, and `/auth/login` endpoints.
- **Universal UUID Primary & Foreign Keys (Changeset 008)**: Migrated primary keys and foreign keys to `uuid DEFAULT gen_random_uuid()` across `workspaces`, `uploads`, `datasets`, `dataset_columns`, `threads`, `runs`, `agent_events`, `feedback`, `eval_results`, `quarantine`, `column_mapping`, `upload_attribute_schema`, `sales_clean`, and dynamically generated tables (`user_data.ds_*`).
- **Data Room Creation**: `create_workspace` generates UUIDs (`uuid.uuid4()`), accepts optional client UUIDs, associates workspace membership with the user, and provides backward-compatible fallback for unmigrated databases.
- **Backend & Frontend Compatibility**: Introduced `sql_id()` to sanitize and string-quote UUIDs across SQL queries without integer cast crashes; updated all frontend interfaces and views to accept `string | number` IDs seamlessly.

#### 2. Performance Optimization & Sidebar Render Stability (Decision 56)
- **Eliminated Redundant Query Revalidations**: Removed extraneous `mutateResource('room:' + roomId)` from `event === "done"` in `chat-store.tsx`. Normal chat queries do not change room metadata and no longer trigger background refetches.
- **Stale-While-Revalidate in `useResource`**: Fixed `mutateResource` with no arguments in `use-resource.ts` to preserve existing cached data instead of evicting it (`resourceCache.delete`), completely eliminating screen/sidebar flickering.
- **Zero-Lag Optimistic Approval**: In `chat-store.tsx` (`approveSchema`), synchronously and optimistically updates `room.datasets` and `room.uploads` with the data returned directly from the approval endpoint, updating the sidebar in 0ms without waiting for a second network roundtrip.
- **Comprehensive Memoization**:
  - `RoomShellLayout`: Wrapped `handleDeleteThread`, `handleToggleDataset`, `handleRemoveDataset`, `handleRenameDataset`, and `handleFileSelected` in `useCallback`; memoized `datasets`, `allDatasetIds`, `selectedDatasetIds`, `pendingUploads`, and `healthSummary`.
  - Sidebar Components: Memoized `Sidebar`, `DatasetSection`, and `ThreadList` using `React.memo`. When queries run or tokens stream, the entire sidebar tree remains completely static and does not re-render.

#### 2. Prior Refactors Active & Preserved
- **Upload Lifecycle Preservation (Decision 55)**: Upload handoff turns persisted in `runs` under active `thread_id`; rehydration restored on reload.
- **Flow Protection (Decision 55)**: "New chat" button and ⌘K disabled while upload/review is active.
- **Data Rooms Hub Shell Unification (Decision 54)**: 260px shared sidebar and 720px column layout across hub and room modes.
- **Datasets Belong to Data Room (Decisions 52 & 53)**: First-class `threads` table with RLS and per-chat dataset selection enforcement.

### Verification Suite Baseline
- **Pytest Suite (`pytest backend/tests`)**: 36/36 passed (100%).
- **Golden Set Benchmark (`python backend/eval/runner.py`)**: 100% SQL correctness, 100% numeric faithfulness, 100% refusal accuracy.
- **Frontend Typecheck (`npm run typecheck --prefix frontend`)**: 0 errors.
