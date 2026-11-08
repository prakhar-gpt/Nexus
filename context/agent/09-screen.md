# 9. The screen

One route, `app/apps/web`. The conversation is the page. `app/apps/web/components/dashboard.tsx` owns the request. `chat-pane.tsx` owns the bubble. `lib/api.ts` owns `readSse` and the `TraceStep` type (`id` optional, plus `tool`, `status`, `ms`, `detail`).

`ask()` in the dashboard:

1. Appends the user line and an assistant message with `text: ""`, `badge: "waiting"`, and no activity.
2. `POST`s `{question}` to `http://localhost:8000/workspaces/{id}/chat`.
3. Reads SSE. Chat cannot use `EventSource` because the route is POST.

| Event | What the dashboard does |
|---|---|
| `step` | Upserts `message.activity` by `id`. A second event for the same id replaces the line. |
| `sql` | Sets `sql` and `rowCount` on that message. |
| `token` | Appends `data.text` to `message.text`. It does not replace the whole string. |
| `check` | Sets the badge from `verified` / kind. |
| `done` | Sets `runId`, `rows`, and, when `answer` is a non-empty string, replaces `text` with that stored sentence. |
| `error` | Replaces the text with a short failure. |

`readSse` splits on a blank line. `data:` is JSON. Trimming the line does not trim spaces inside the JSON string. Do not `trim()` the token before appending it.

`AssistantMessage` in `chat-pane.tsx`:

- Activity lines are `message.activity` with `checker` removed. Each line is `step.detail`.
- While `badge` is `waiting` and there is no text and no activity, it shows "Looking at the table…". That string is only the gap before the first tool or the first token. It is not an answer.
- `message.text` goes through `AnswerBody`: `react-markdown`, `remark-gfm`, `remark-breaks`. Headings are flattened. Links must be `http` or `https`. Images render nothing.
- A caveat or a refusal is one sentence under the answer (`NOTE`). A verified answer has no badge.
- "Show the query" opens the SQL, the row count, the chart, and the CSV export. The chart is `answer-chart.tsx`, loaded with `ssr: false`. It is not on screen until the query is opened.

History on load is `GET /workspaces/{id}`, field `turns`, the last 20 runs. Those bubbles are the stored `answer`, which already has spaces and markdown. They do not replay the token stream. A live bubble that disagrees with a refresh is a token bug in [08-stream.md](08-stream.md), not a second renderer.

The sidebar (`data-pane.tsx`) is the room: name, row count, date range, file, mapping confirmation when one is pending, quarantine when rows exist, and the golden-set score. It is hidden on a narrow viewport unless the room name is open or a mapping is waiting. There is one `DataPane`. There is no trace pane and no document chip.

Theme and type are not part of the turn. They are the tokens in `app/apps/web/app/globals.css` (white field, warm stone text, red primary, `--radius: 0`) and JetBrains Mono on `--font-sans`. Dark mode does not follow the operating system. Decision 24.

Do not send a suggestion click while checking the page. The three suggestions in `components/suggestions.ts` call the model immediately.
