# Roadmap (4-Week Build)

Part-time estimate from the v2 document: 3 to 4 weeks. If time runs short, ship Weeks 1–3 plus a minimal UI. Cut in this order: Neo4j, PySpark, Redis, PDF support. Keep the SQL path, the checker, the Eval panel, and upload validation.

Week 4 Docker Compose packages the application. The database stays the existing local PostgreSQL (Decision 5) until a later decision says otherwise.

## Week 1 — current, not started

Postgres + Superstore loaded into `sales_clean`. Read-only `run_sql`. A 25-question golden set. The Python number checker. A CI eval script.

## Week 2

Ingestion: parsing, header detection, RapidFuzz mapping with LLM fallback, quarantine. All six test files pass.

| File | Expected result |
|---|---|
| 1 Clean sales table | Accepted, auto-mapped |
| 2 Junk rows above the header | Header detected, or the user is asked |
| 3 Messy names and text numbers | Mapped with confirmation, then cleaned |
| 4 Empty or single-column file | Rejected with a reason |
| 5 Unrelated data (payroll) | Rejected at domain fit |
| 6 Formula-like and prompt-injection cells | Stored as inert data; the agent is unaffected |

## Week 3

Single-dashboard Next.js UI. FastAPI SSE. Trace panel. Data health. Answer cards with source chips.

## Week 4

One role-specific add-on, chosen from the list below. Docker Compose. GitHub Actions running eval on push. A two-minute demo.

Demo beats to cover: a clean upload and a bad upload with its quarantine report; a mapping confirmation; a losing-sub-category question with trace, chart, SQL chip, and verified badge; a refusal; a document question with its source passage; Eval scores before and after the checker.

Talking points live with that demo: why SQL is the source of truth, where the checker changed a number, local versus hosted model cost and latency, what would change at CoE scale, and how tests kept the AI-assisted build honest.

## Add-ons — pick one or two

The choice depends on the first role, which is still open (`active-context.md`).

| Add-on | Best-fit role | Effort |
|---|---|---|
| Survey validation (speeders, straight-liners, duplicates) | PEG Alpha | 1–2 days |
| Provider switch and model comparison on the golden set | PEG AI Solutions | 1 day |
| Tableau-style CSV/Excel export of SQL output | Capabilities Tech Hub | 0.5 day |
| Neo4j graph: category > sub-category > product > brand | Retail CoE | 3–5 days; cut first |
| One PySpark job on Olist, with benchmark logs, no live cluster | PEG Alpha | 2–3 days |

## Datasets by week

Week 1 uses Superstore. Week 2's upload demo adds Online Retail II. Olist is only needed if the PySpark add-on is chosen. PDFs are Week 4 RAG content and are on the cut list.

## Progress

- 2026-11-08: v2 product document incorporated into `architecture.md`, `agents.md`, `decisions.md`, and this file. No week has been executed. No DDL has been applied.
- 2026-11-08: Week 1 DDL and Superstore loader written (`app/infra/schema.sql`, `app/infra/load_superstore.py`). Not applied. Local PostgreSQL 18 requires a password, and none is available to the session.
- 2026-11-08: User created empty `nexus_db`. Schema and Superstore load still blocked on the `postgres` role password.
- 2026-11-08: Applied `app/infra/schema.sql` and loaded Superstore. `sales_clean` has 9800 rows, order dates 2015-01-03 through 2018-12-30, revenue 2261536.78. Quantity, unit price, discount, cost, profit, and channel are null.
