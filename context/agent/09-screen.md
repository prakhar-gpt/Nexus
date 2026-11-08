# 9. The screen

One route, `frontend/`. The conversation is the screen. The design follows Claude.ai: calm, quiet, text-first, and confident. See `context/design-language.md` for the complete design language specification.

`frontend/components/dashboard.tsx` owns the request and state switching between Data Rooms Hub (`WorkspacesView`) and Data Room Chat (`ChatPane` + `Sidebar`). `frontend/lib/api.ts` owns `readSse` and the `TraceStep` type (`id` optional, plus `tool`, `status`, `ms`, `detail`).

`ask()` in the dashboard:

1. Appends the user line (accent background, max 80% width) and an assistant message with `text: ""`, `badge: "waiting"`, and empty activity.
2. `POST`s `{question, thread_id}` to `http://localhost:8000/workspaces/{id}/chat` with an `AbortController`.
3. Reads SSE. Chat cannot use `EventSource` because the route is POST.

| Event | What the dashboard does |
|---|---|
| `step` | Upserts `message.activity` by `id`. Displays in `ToolLine` without circle dots, disappearing on first token. |
| `sql` | Sets `sql` and `rowCount` on that message. |
| `token` | Appends `data.text` to `message.text` with a 2px blinking caret at stream head. Does not trim spaces. |
| `source` | Stores citation chips (e.g. "Document, p. 4"). |
| `check` | Sets badge (`verified`, `caveat`, `refused`), `untraced` figures, and missing measures. Verified answers remain completely unbadged. |
| `done` | Sets `runId`, `rows`, and final answer text. Triggers thread turn increment and title auto-naming. |
| `error` | Displays inline destructive failure banner with Retry button. |

`AssistantMessage` in `chat-pane.tsx`:

- Set as open prose with no bubble and no background fill, 16px size, 1.65 line-height, centered 720px max column. Small mono "Nexus" label appears above only the first assistant turn.
- `ToolLine` renders tool steps (e.g. "Looking at the columns…", "Running a query…", "Calculating…") without decorative bullets. Disappears completely upon token arrival.
- Progressive markdown rendering via `ReactMarkdown` (`remark-gfm`, `remark-breaks`). Tables have hairline borders and tabular-nums.
- Verified answers are unbadged. Caveat (amber) and Refused (red) display 10% opacity status badges with explanatory tooltips.
- `AuditBar` toggles `QueryPanel` (smooth inline expansion): read-only SQL syntax highlighting with copy, compact result table with TSV copy, lazy-loaded Recharts bar chart (220px, no gridlines, thin axes, hover primary), and up/down voting with optional reason input.
- `Composer` is pinned at the bottom in a 720px card container with auto-growing textarea (1-8 lines), primary focus ring, up-arrow query recall, `/` global hotkey, and send/stop toggle.
