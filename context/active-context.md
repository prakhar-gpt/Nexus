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

#### 1. Performance Optimization & Sidebar Render Stability (Decision 56)
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
