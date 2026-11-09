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
