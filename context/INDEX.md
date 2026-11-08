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
| Build plan, phases, milestones | roadmap.md | Update after completing a phase |
| What's in progress / unresolved right now | active-context.md | Overwrite, don't append |
| Where to start / which doc | This INDEX | Always read first |

## Folder map

context/
├── INDEX.md              ← start here
├── architecture.md       ← system design and stack
├── agents.md             ← module rules and responsibilities
├── decisions.md          ← dated decision log
├── roadmap.md            ← build plan and progress
└── active-context.md     ← current unresolved state

## Default search scope

Search only `app/` and the specific `context/` files relevant to the
task. Do not preload the entire `context/` folder into every prompt.
