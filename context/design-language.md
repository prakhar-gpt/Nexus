# Nexus Design Language: Calm, Text-First, and Defensible

Nexus is built for commercial due diligence analysts. The design language follows Claude.ai: calm, quiet, text-first, and confident. The product promise is **defensible answers**. Every design decision makes the answer easy to read and audit; nothing else competes for attention.

---

## 1. Core Principles

1. **The conversation is the screen.** Everything else is quiet.
2. **Content over chrome.** Hairline borders (`border-border`), whitespace, and typographic weight instead of drop shadows or heavy boxes.
3. **Progressive disclosure.** SQL, row counts, charts, and ETL detail remain hidden until explicitly requested.
4. **One primary accent.** The warm red token (`--primary`) is reserved strictly for primary actions, focus rings, destructive triggers, and refused states. Never for decoration.
5. **Honest states.** Every async action exposes loading, success, and failure states clearly. Failed uploads, dropped streams, unsaved mappings, or failed ratings show specific inline guidance and never masquerade as successful.
6. **Functional and subtle motion.** 120–180ms ease-out, opacity shifts, and maximal 4px translations. Respects `prefers-reduced-motion`.
7. **No noise.** Zero emojis, zero gradients, zero heavy drop shadows, zero decorative illustrations, and zero marketing copy.

---

## 2. Palette & Tokens

The color system is fixed: white field, warm stone text and surfaces, and an inverted dark mode toggled by class without OS-following.

```css
/* Status tokens added in globals.css (passing WCAG AA on warm stone) */
:root {
  --ok: oklch(0.52 0.13 145);      /* Muted forest green */
  --warn: oklch(0.53 0.15 65);     /* Warm amber ochre */
}

.dark {
  --ok: oklch(0.72 0.13 145);
  --warn: oklch(0.75 0.14 65);
}
```

- **Surfaces**: `background` for chat canvas, `sidebar` for navigation pane, `card` / `popover` for cards and modals.
- **Hairlines**: `border` / `sidebar-border` (1px everywhere).
- **Secondary**: `muted-foreground` for captions, timestamps, and secondary metadata.
- **Status Badges**: 10% opacity background (`bg-ok/10`, `bg-warn/10`, `bg-destructive/10`) with matching hairline borders.
  - Verified answers: Kept completely unbadged and calm.
  - Caveat: Warn-tinted badge with untraced numbers tooltip.
  - Refused: Destructive-tinted badge with missing measure tooltip.

---

## 3. Typography & Shapes

- **Font**: JetBrains Mono (`--font-sans`, `--font-mono`).
- **Radius**: Square corners (`--radius: 0`).
- **Weights**: Only 400 and 500 (600 reserved strictly for page titles).
- **Numerics**: `tabular-nums` applied to all figures, dates, row counts, and percentages.
- **Assistant Prose**: Set as open prose with no bubble, no background fill, 16px size, 1.65 line-height, and a 720px max column width.
- **Grids & Widths**: 4px grid. Centered 720px column for conversation (`max-w-[720px] mx-auto`); 960px centered column for the Data Rooms Hub (`max-w-[960px] mx-auto`).

---

## 4. Screen Specifications

### Screen 1: Data Rooms Hub (`WorkspacesView`)
- **Top Row**: 56px slim bar with bottom hairline. Left: "Nexus" wordmark + "Commercial due diligence & retail analytics". Right: Auth status (ghost profile dropdown or "Sign in") + primary "New data room" button.
- **Body**: 28px page title with muted summary sentence. Responsive 1/2/3-column grid (16px gap).
- **Action Tile**: Dashed hairline border, centered plus icon, tints on hover to `accent`.
- **Room Card**: Card surface with 1px hairline, 20px padding. Displays name, active indicator, file count, query count, creation date, hover-reveal trash icon (opens `ConfirmDialog`), and "Open →" link.
- **Empty State**: Centered text block with primary action, no illustration.
- **Loading State**: 3 skeleton cards matching card height.
- **Error State**: Inline banner with retry button.

### Screen 2: Data Room Chat (`ChatPane` & `Sidebar`)
- **Sidebar (260px)**:
  1. Top navigation: "← Data rooms" button + "Nexus" wordmark.
  2. Data room block: Room name, row count + date range (tabular mono), "Dataset" modal trigger (with warn dot if mapping/quarantine needs attention), and golden-set eval score.
  3. "New chat" button: Full-width outline with `⌘K` keyboard shortcut.
  4. "Chats" section: Single-line truncated titles, 2px foreground active left marker, turn count, hover trash button. Grouped by Today / Yesterday / Earlier when > 8 threads.
  5. Profile footer: Avatar initials, name, email, role badge, theme toggle (light/dark), and working logout.
- **Chat Canvas**:
  - Empty State: Centered 32px heading "What should we look at?" with 4 plain suggestion rows separated by hairlines.
  - User Messages: Right-aligned with `accent` background fill, max 80% width.
  - Assistant Messages: Open prose, no bubble, left-aligned, full width. Small "Nexus" label above only the first assistant turn.
  - Streaming Tool Line: Single quiet muted line showing current step (e.g. "Looking at the columns…", "Running a query…"). Removed immediately upon arrival of first token.
  - Streaming Caret: Blinking 2px hairline cursor at stream head. Auto-scroll stays pinned only if user is within 80px of bottom; otherwise floating "↓ New content" pill appears.
  - Audit Bar: Positioned below answer with "Show the query" accordion, row count chip, Caveat/Refused badges, TSV export, SQL copy, vote buttons (with reason input on downvote), and lazy-loaded Recharts bar chart (220px, no gridlines, thin axes, foreground bars with hover primary).
  - Composer: Pinned centered 720px card, auto-growing 1–8 lines, primary focus ring, up-arrow query recall, `/` global focus hotkey, and send/stop toggle.

---

## 5. Modals & Dialogs

All dialogs share: `popover` background, 1px border, `--radius: 0`, 24px padding, 40% black backdrop with 2px blur, trapped focus, Esc to close, right-aligned Cancel (ghost) and primary action.

1. **`CreateWorkspaceModal`**: Autofocused name input with inline error handling.
2. **`ConfirmDialog`**: Shadcn `AlertDialog` with destructive styling for room and thread deletions.
3. **`AuthModal`**: Shadcn `Tabs` for "Sign in" and "Create account" with field validation, enter-to-submit, and button spinner.
4. **`DataRoomModal` (720px wide)**:
   - Summary: Rows, date range, last upload.
   - Dropzone: Drag-and-drop zone with MIME and 50MB validation.
   - Pipeline Stepper: Horizontal desktop / vertical mobile progress tracker ("Checking file → Reading sheet → Matching columns → Loading rows").
   - Column Mapping: Uncertain rows (<70%) shown first with warn-tinting; auto-mapped rows (≥70%) collapsed under expander; confirm button disabled until resolved.
   - Quarantine: Quarantined anomaly table with CSV report download.

