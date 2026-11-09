# Nexus Design Language: Calm, Text-First, and Defensible

Nexus is built for commercial due diligence analysts. The design language follows Claude.ai: calm, quiet, text-first, and confident. The product promise is **defensible answers**. Every design decision makes the answer easy to read and audit; nothing else competes for attention.

---

## 1. Core Principles

1. **The conversation is the screen.** Everything else is quiet.
2. **Content over chrome.** Hairline borders (`border-border`), whitespace, and typographic weight instead of drop shadows or heavy boxes.
3. **Progressive disclosure.** SQL, row counts, charts, and load detail stay hidden until requested.
4. **One primary accent.** The warm red token (`--primary`) is reserved strictly for primary actions, focus rings, destructive triggers, and refused states. Never for decoration.
5. **Honest states.** Every async action exposes loading, success, and failure. Failed uploads, dropped streams, unsaved schema edits, and failed ratings show specific inline guidance with a next step and never look successful. A spinner never outlives a failure.
6. **Functional and subtle motion.** 120–180ms ease-out, opacity shifts, 4px max translation. Respect `prefers-reduced-motion`.
7. **No noise.** Zero emojis, zero gradients, zero heavy shadows, zero decorative illustrations, and zero marketing copy.
8. **Always visible progress.** Anything that takes more than a moment shows what is happening, in plain language, from real events. Never fake progress.

---

## 2. Palette & Tokens

The color system is fixed: white field, warm stone text and surfaces, and an inverted dark mode toggled by class, not OS-driven.

```css
/* Status tokens in globals.css (passing WCAG AA on warm stone) */
:root {
  --ok: oklch(0.52 0.13 145);      /* Muted forest green */
  --warn: oklch(0.53 0.15 65);     /* Warm amber ochre */
}

.dark {
  --ok: oklch(0.72 0.13 145);
  --warn: oklch(0.75 0.14 65);
}
```

- **Surfaces**: `background` for canvas, `sidebar` for navigation pane, `card` / `popover` for cards and dialogs.
- **Hairlines**: `border` / `sidebar-border` (1px everywhere).
- **Secondary**: `muted-foreground` for captions, timestamps, and secondary metadata.
- **Status Badges**: 10% opacity background (`bg-ok/10`, `bg-warn/10`, `bg-destructive/10`) with matching hairline borders.
  - Verified answers: Kept completely unbadged and calm.
  - Caveat: Warn-tinted badge with untraced numbers tooltip.
  - Refused: Destructive-tinted badge with missing measure tooltip.

---

## 3. Typography, Shapes & Containers

- **Font**: Playfair Display for all headers (`h1`–`h6`, `--font-heading`); JetBrains Mono for body, code, and UI elements (`--font-sans`, `--font-mono`).
- **Radius**: Square corners (`--radius: 0`).
- **Weights**: Only 400 and 500 (600 reserved strictly for page titles).
- **Numerics**: `tabular-nums` applied to all figures, dates, row counts, and percentages.
- **Assistant Prose**: Open prose with no bubble, no background fill, 16px size, 1.65 line-height, and a 720px max column width.
- **Unified App Shell**: 4px grid. All screens use the same application shell: a left sidebar (260px width) plus a main pane. The main pane content is set in a single shared 720px column (`max-w-[720px] mx-auto px-4 sm:px-6`).
  - No separate top header bars on root hubs.
  - No custom 960px or wide-card grid layouts.
  - Below the tablet breakpoint (md: 768px), the sidebar collapses into a drawer opened by a menu button in a slim top bar that displays the "Nexus" wordmark.
  - Verify layout and left-edge alignment at 1920, 1280, and 390px.

---

## 4. Layout & Alignment Rules

1. **Unified app shell.** All views share the same left sidebar shell and 720px main pane column. No separate top header bar or multi-container drift across screens. Verify at 1920, 1280, and 390px.
2. **Consistent alignment.** Alignment is consistent within a view: if the heading is left-aligned, empty states and panels are left-aligned too. No mixed centered/left layouts.
3. **One primary action per view.** A view shows a single primary (red) call to action. When a page is empty, the empty-state button is the primary action and the header/sidebar button is quiet outline. When content exists, the action in the sidebar becomes primary. Never show two identical primary buttons.
4. **Empty states.** Sit directly under the page heading (not vertically centered in the viewport), use the dashed-border panel pattern (same as "Add a dataset to start"), and are left-aligned: title, one line of text, one button.
5. **No horizontal page scroll.** Wide tables scroll inside their own container with a sticky header. No horizontal scroll at 390px.
6. **Truncation and text safety.** Long names and cell text truncate with a title tooltip. All file-derived text is rendered as text, never HTML.

---

## 5. Screen Specifications

### Screen 1: Data Rooms Hub (`WorkspacesView`)
The Data Rooms Hub uses the exact same shell as the room view: a 260px left sidebar and a main pane in the shared 720px column. There is no separate top header bar.

- **Sidebar (hub mode)**:
  1. Top: "Nexus" wordmark in the same position as in room mode (`text-xs font-medium tracking-tight text-sidebar-foreground`).
  2. **+ New data room** button, full-width, same position and size as "New chat" in room mode:
     - Primary (red) button (`bg-primary text-primary-foreground`) when at least one room exists.
     - Quiet outline button (`border border-sidebar-border bg-sidebar text-sidebar-foreground hover:bg-sidebar-accent`) when zero rooms exist (the empty-state panel owns the primary action).
  3. Section label **Data rooms**, then one row per room:
     - Single-line truncated name (`text-xs font-medium truncate`).
     - Quiet secondary line (`text-[11px] font-mono tabular-nums text-muted-foreground`): dataset count, last activity date.
     - Hover-reveal trash icon that triggers `ConfirmDialog` with accessible label (`"Delete data room {name}"`).
     - Clicking a row navigates into that room (`/rooms/{id}`). Keyboard accessible with visible focus and Enter-to-open.
     - Navigation landmark `<nav aria-label="Data rooms">` with `aria-current="page"` on active room (none on the hub).
  4. Sorting: Sort by last activity, newest first. Group nothing unless there are more than 8 rooms (then group by Today / Yesterday / Earlier like Chats).
  5. Footer: Existing profile footer (avatar initials, name, email, role badge, theme toggle, logout). When signed out, show a "Sign in" button that opens `AuthModal` in the same spot.
  6. Loading: 3 skeleton rows. Error: inline banner with retry inside the list area.

- **Main Pane (hub mode)**:
  - Left-aligned in the shared 720px column, vertically placed like the chat empty state (top-aligned, not vertically centered in the viewport).
  - Heading (36–48px / text-4xl sm:text-5xl, 600, leading-tight, tracking-tight): `"Welcome, {first name}"`. If signed out or no name: `"Welcome"`.
  - When rooms exist: one muted line under the heading: `"Select a data room to continue, or create a new one."`
  - With zero rooms: heading `"Welcome, {first name}"`, and directly below it:
    - Title: `"No data rooms yet"`
    - Text: `"Create a workspace, add a spreadsheet, and ask questions in plain English."`
  - No room cards, no action tile, no extra buttons in the main pane.
  - Footer line: `"Answers are checked against query results. Verify before sharing."` pinned at the bottom.

- **Responsive**:
  - Below the tablet breakpoint (md: 768px), the sidebar becomes a drawer opened by a menu button in a slim top bar that displays the "Nexus" wordmark. Same behavior in hub and room modes. No horizontal scroll at 390px.

### Screen 2: Data Room (`ChatPane` and `Sidebar`)
- **Sidebar (room mode, 260px)**:
  1. Top navigation: "← Data rooms" and the "Nexus" wordmark.
  2. Data room name.
  3. **Datasets section.** One row per dataset: checkbox (whether the current chat may read it), label, grain line ("One row = an order line"), row count, and a quiet "N set aside (download)" link when rows were quarantined. A row's overflow menu has Rename, Download quarantine, and Remove (confirm dialog listing what is deleted). Pending uploads show "Analyzing…" or "Needs review" instead of a checkbox, and clicking one reopens its setup card. A quiet "+ Add dataset" control opens the file picker. Datasets belong to the data room and are shared by all chats.
  4. "New chat" button (full-width outline, `⌘K`).
  5. "Chats" list: single-line truncated titles, 2px foreground active marker, turn count, hover trash. Grouped Today / Yesterday / Earlier when > 8 chats. Chats contain only questions and answers.
  6. Profile footer: avatar initials, name, email, role badge, theme toggle, logout.
- **Setup card** (upload and schema review): rendered in the main pane above the composer area or in place of the empty state. It is never a chat message and never stored as chat history.
  - Uses the shared steps list (`agent-steps`), one plain-language line per real event, with a live timer after 3 seconds and "Still working. Last step: …" after 15 seconds. No pill stepper, progress bar, or percentage in the header.
  - Authored as "Schema Architect" (small label). Failures show one red line with the reason and a next step.
  - On completion the profiling lines collapse to "Inspected 12 columns · 6 checks", expandable.
  - **Review view:** the grain sentence ("One row = …") is editable and visually primary. A compact column table (name, type, role, include) with details (description, parse rate, null rate, confidence) in an expandable row. Warnings are one amber line each, errors red. **Approve and create table** is disabled while errors exist, with the reason visible next to it. Quiet **Regenerate with a hint** (max 3) and **Reject**. Edits save server-side with debounce.
  - On Approve the card streams "Creating table…" and "Loading rows…" with real progress, then collapses and is replaced by the dataset row in the sidebar (brief highlight). Reject removes the card.
- **Chat canvas**:
  - **Before any dataset exists:** composer disabled with the hint "Add a dataset to start", and the dashed add-dataset panel in the main pane.
  - **After:** empty chat shows a short confirmation line ("Loaded Superstore · 9,994 rows · one row = an order line") and up to 3 deterministic suggestion chips derived from the checked datasets' column roles. Clicking one sends it as a normal user turn. If no dataset is checked, the composer shows "Select a dataset to ask about" and send is blocked.
  - **User messages:** right-aligned, `accent` fill, max 80% width.
  - **Assistant messages:** open prose, no bubble, left-aligned, full width. Small "Nexus" label above the first assistant turn.
  - **Live steps:** Nexus streams its tool steps through the same shared steps component as the Schema Architect. Once the answer starts streaming, the steps collapse behind a quiet disclosure.
  - **Streaming caret and scroll:** blinking 2px hairline caret; auto-scroll pinned only within 80px of the bottom, otherwise a floating "↓ New content" pill.
  - **Audit bar:** "Show the query" accordion (which also names the dataset queried), row count chip, Caveat/Refused badges, TSV export, SQL copy, vote buttons, lazy Recharts bar chart (220px, no gridlines).
  - **Composer:** pinned centered 720px card, auto-growing 1–8 lines, paperclip for adding a dataset, drag-and-drop anywhere on the pane (subtle "Drop to upload" overlay), up-arrow recall, `/` focus hotkey, send/stop toggle.

---

## 6. Modals & Dialogs

All dialogs share: `popover` background, 1px border, `--radius: 0`, 24px padding, 40% black backdrop with 2px blur, trapped focus, Esc to close, right-aligned Cancel (ghost) and primary action.

1. `CreateWorkspaceModal`: autofocused name input, inline errors.
2. `ConfirmDialog`: shadcn `AlertDialog`, destructive styling, used for deleting rooms, chats, and datasets. Dataset removal lists what is deleted (table, catalog rows, quarantine rows).
3. `AuthModal`: tabs for Sign in and Create account, validation, enter-to-submit, button spinner.

There is no upload modal. Upload and schema review live in the setup card. Column mapping no longer exists.

---

## 7. Copy & Naming Rules

- **Plain English & No Jargon**: Copy is deterministic, plain English, and describes what the user does ("add a spreadsheet, ask questions"), never implementation details ("run SQL queries"). No LLM-written labels, step text, or errors.
- **Product-Aligned Scope**: Copy must match the current product: any spreadsheet goes through the Schema Architect; datasets belong to the data room; users ask in plain English and Nexus shows the query behind every answer. Remove "sales data"-only wording.
- **Strict Naming Hierarchy**: The three user-facing nouns are **data room**, **dataset**, and **chat**. Do not introduce synonyms (workspace, thread, table, upload) in UI copy.
- **Agent Identity**: "Nexus" is the product and the chat agent. "Schema Architect" appears only in the setup card.
- **Data Integrity**: Nexus never claims to have created or changed a dataset. Datasets are created only after the user approves.
- **Canonical Strings**:
  - Hub welcome heading: `"Welcome, {first name}"` (or `"Welcome"`)
  - Hub with rooms subtitle: `"Select a data room to continue, or create a new one."`
  - Hub empty title: `"No data rooms yet"`
  - Hub empty text: `"Create a workspace, add a spreadsheet, and ask questions in plain English."`
  - Composer, no dataset: `"Add a dataset to start"`
  - Composer, none checked: `"Select a dataset to ask about"`
  - Footer: `"Answers are checked against query results. Verify before sharing."`

---

## 8. Dev-Only Artifacts

Framework dev indicators (such as the Next.js static route and build activity badges) are disabled in development so they never cover UI elements (`devIndicators: false` in `next.config.ts`).

---

## 9. Before Merging UI Changes (Checklist)

- [ ] **Shared shell & container**: Sidebar (260px) and main pane (720px column) share the unified layout (verify at 1920, 1280, 390px)
- [ ] **One primary action**: Exactly one primary action per view; no duplicate primary buttons (outline in sidebar when view is empty)
- [ ] **Empty-state pattern**: Empty states sit directly under the heading and use the dashed-panel pattern, left-aligned
- [ ] **Copy rules**: Plain English, no jargon, describes user actions without implementation details
- [ ] **Naming hierarchy**: Uses only data room / dataset / chat (no workspace, thread, table, upload); canonical strings reused
- [ ] **Honest states**: Async actions show loading, success, and failure; no stuck spinners; failures have a next step
- [ ] **Real progress**: Long-running work shows live steps from real events
- [ ] **Both palettes**: Light and dark palettes verified (dark is inverted hues, not OS-driven)
- [ ] **Narrow viewport**: Responsive down to 390px with mobile drawer toggle; no horizontal page scroll
- [ ] **Focus & accessibility**: Keyboard operable, visible focus ring, `role="alert"` on errors, `aria-live="polite"` on steps, `aria-current="page"` on active rooms
- [ ] **Dev indicators**: Framework dev indicators disabled in development (`devIndicators: false`)
- [ ] **File-derived text**: Rendered strictly as text, never HTML
- [ ] **Refresh test**: Reload at each state and confirm nothing duplicates or disappears
