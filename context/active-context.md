Created At: 2026-11-09T00:35:50+05:30
Updated At: 2026-11-09T06:41:00+05:30

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

#### 1. Upload Lifecycle Preservation, Review Rehydration, and Sidebar Dataset Wiring (Decision 55)
- **Sidebar Dataset Wiring**:
  - Connected `datasets`, `selectedDatasetIds`, `activeThreadId`, `pendingUploads`, and action handlers (`onToggleDataset`, `onRemoveDataset`, `onRenameDataset`, `onAddDatasetClick`) into `frontend/app/(app)/rooms/[roomId]/layout.tsx`.
  - The left sidebar permanently renders every loaded dataset (`Datasets (N)`) with grain line, row count, quarantine download link, and per-chat checkboxes.
- **Instant Chat History Rendering**:
  - In `ExistingThreadPage` (`frontend/app/(app)/rooms/[roomId]/c/[threadId]/page.tsx`), hydrated `initThreadTurns` immediately from in-memory `room.turns` on mount. Chats switch and render with 0ms delay without a full-screen pulse skeleton.
- **Upload Handoff Persistence Across Reload**:
  - In `backend/api/services/upload_service.py` (`approve_upload_schema`), persisting a clean, human-readable turn into `runs` under the active `thread_id`: `question: "Uploaded dataset: <name>"`, `answer: "I've loaded <TableLabel>..."`, and `checker_result` with `handoff_data`.
  - In `frontend/lib/chat-store.tsx` (`turnsToMessages`), mapped upload handoff turns to user upload message and assistant message with interactive question chips, preserving the entire upload conversation across page reloads without raw JSON or split threads.
- **Upload / Review Stage Rehydration on Reload**:
  - Implemented `rehydrateUpload` in `frontend/lib/chat-store.tsx`. If an upload is pending review (`needs_schema_review`) or in progress (`profiling`), refreshing the page on `/rooms/[roomId]` or `/rooms/[roomId]/c/[threadId]` retrieves the schema proposal from `/uploads/{id}/schema` and mounts the `SchemaArchitectCard` in review mode.
- **Flow Protection During Upload & Review**:
  - Disabled the "New chat" button and blocked `⌘K` while an upload is active or in schema review (`isUploadRunning || isReviewPending`) to prevent breaking the profiling or review flow.
- **Tool Author Label Cleanup**:
  - Removed file name from the author badge (`Nexus · {fileName}` -> `Nexus`) in `frontend/components/schema-architect-card.tsx`.
- **Database Schema Alignment**:
  - Aligned `INSERT INTO runs` in `upload_service.py` with PostgreSQL schema `(workspace_id, question, answer, checker_result, latency_ms)`. Added `Query` import in `backend/api/routers/uploads.py`.

#### 2. Data Rooms Hub Shell Unification (Decision 54)
- **Unified App Shell**: Redesigned the Data Rooms Hub (`WorkspacesView`) to use the exact same shell as the room view: a 260px left sidebar and a main pane in the shared 720px column.
- **Shared Sidebar Component (`Sidebar`)**: Unified `"hub"` and `"room"` content modes in one component with `RoomList`, dataset counts, activity dates, hover-reveal delete, and `UserProfileFooter`.
- **Main Pane Welcome & Empty State**: Left-aligned in the 720px column.

#### 3. Datasets Belong to Data Room, Not a Chat (Decisions 52 & 53)
- Dedicated `threads` table with RLS and `selected_dataset_ids bigint[]`.
- Server-side per-chat dataset selection strictly enforced in API, `get_schema`, and AST guard in `run_sql`.
- Atomic dataset cascade on removal.

### Verification Suite Baseline
- **Pytest Suite (`pytest backend/tests`)**: 36/36 passed (100%).
- **Golden Set Benchmark (`python backend/eval/runner.py`)**: 100% SQL correctness, 100% numeric faithfulness, 100% refusal accuracy.
- **Frontend Typecheck (`npm run typecheck --prefix frontend`)**: 0 errors.
