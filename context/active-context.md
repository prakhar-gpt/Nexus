The question path is documented in `context/agent/`. Start at `context/agent/README.md`. Each step has its own file detailing entry, model selection, thread state, model routing, tools execution, SQL execution, checker verification, streaming, and UI rendering. The complete design system is documented in `context/design-language.md`.

The backend is fully modularized with strict separation of concerns across `app/packages/agent/` (`state.py`, `formatting.py`, `tools/`, `nodes/`, `graph.py`) and `app/apps/api/` (`schemas.py`, `sse.py`, `services/`, `routers/`, `main.py`).

The frontend redesign embodies the Claude.ai design language (calm, text-first, defensible):
1. **Data Rooms Hub (`WorkspacesView`)**: Clean 960px container, slim 56px top row, first-tile "New data room" dashed action, and responsive room cards with file/query metrics, date, and delete confirmation.
2. **Focused Chat Interface**: Centered 720px column. Assistant answers are rendered as open prose (no bubbles, no background, 16px/1.65 line-height). Verified answers remain completely unbadged. Tool lines display quietly without circle dots.
3. **Progressive Audit Disclosure**: Inline `AuditBar` toggling SQL syntax highlighting, compact result table with TSV copy, lazy-loaded Recharts bar chart, source references, and up/down feedback with optional reason input.
4. **Dataset Management (`DataRoomModal`)**: 720px modal featuring dropzone validation, pipeline stepper (safety → structure → mapping → load), uncertain column mapping table (<70% confidence), and quarantine anomaly table with CSV download.
5. **Fixed Warm Stone Palette**: Preserved existing token hierarchy with only two semantic status tokens (`--ok` and `--warn`) passing WCAG AA. JetBrains Mono font and square corners (`--radius: 0`).

The UI runs on `http://localhost:3000` and the FastAPI backend runs on `http://localhost:8000`.

Unresolved / Planned for Implementation:
- **Deterministic Python Math Tool (`run_python`)**: Sandboxed execution for compound growth and statistical metrics, registering outputs into `state` and expanding `checker.py` to trace Python results without caveats.
- **Dynamic Dataset Column Support (`attributes JSONB`)**: Update `sales_clean` with a JSONB column to preserve arbitrary client columns dynamically while retaining canonical anchors (`order_date`, `revenue`/`quantity`).
- **CI & Deployment (Week 4)**: GitHub Actions workflow for `app/eval/runner.py` regression checks on push, and Docker Compose packaging.
- **Knowledge Base / Document Q&A**: pgvector semantic retrieval over PDF diligence memos.
- The Superstore extract contains nulls for `quantity`, `unit_price`, `discount_pct`, `cost`, `profit`, and `channel`; the agent continues to refuse those queries while the deterministic checker acts as backstop.
