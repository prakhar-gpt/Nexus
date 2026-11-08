# Nexus — Context Index

Read this file first in every new chat. Then open ONLY the files that
match the task. Do not load this whole folder.

## How to use this folder

1. Match the question to a row in Routing.
2. Read that file. Follow its links if you need more.
3. After a session that changes product understanding, follow the
   Session close protocol in `.cursorrules`.

The 8 November 2026 v2 product document is incorporated across the
files below. A later file with the same text was checked on 8 November
2026 and did not change these notes. There is no second copy in this folder.

## Routing

| If the task is about… | Read | Notes |
|---|---|---|
| System design, stack, patterns | architecture.md | Check before structural changes |
| Module roles, responsibilities, rules | agents.md | Check before touching unfamiliar code |
| Past decisions, tradeoffs, rejected alternatives | decisions.md | Append after approved decisions |
| Design language, tokens, typography, UI patterns | design-language.md | Claude-like design system and specs |
| Build plan, phases, milestones | roadmap.md | Update after completing a phase |
| What's in progress / unresolved right now | active-context.md | Overwrite, don't append |
| How a question becomes an answer | agent/README.md | Read the step files in order the first time. Then open only the step you are changing |
| Where to start / which doc | This INDEX | Always read first |

## Folder map

context/
├── INDEX.md              ← start here
├── architecture.md       ← system design and stack
├── agents.md             ← module rules and responsibilities
├── decisions.md          ← dated decision log
├── design-language.md    ← Claude-like design system & specs
├── roadmap.md            ← build plan and progress
├── active-context.md     ← current unresolved state
└── agent/                ← one file per step of a question
    ├── README.md         ← read this before the step files
    ├── 01-entry.md       ← POST /chat to stream()
    ├── 02-model.md       ← Groq, then OpenRouter, then DeepSeek
    ├── 03-thread.md      ← workspace memory
    ├── 04-choose.md      ← the model picks the tool
    ├── 05-tools.md       ← get_schema, run_sql, read_kb
    ├── 06-sql.md         ← guard, reader role, 200 row cap
    ├── 07-checker.md     ← numbers must trace to this turn
    ├── 08-stream.md      ← tool lines and tokens
    └── 09-screen.md      ← how the chat paints them

## Default search scope

Search only `app/` and the specific `context/` files relevant to the
task. Do not preload the entire `context/` folder into every prompt.
