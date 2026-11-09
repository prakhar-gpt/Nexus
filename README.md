# Nexus

Nexus is a retail data room copilot designed for consulting analysts and commercial due diligence teams. It ingests retail and commercial spreadsheets (CSV/XLSX), dynamically profiles their schema and grain, generates custom PostgreSQL tables, and answers analytical questions with defensible, AST-guarded SQL queries and verified arithmetic.

Every commercial figure cited in an answer must originate from database rows or an isolated Python execution sandbox, verified by a deterministic number checker before being displayed.

---

## Core Capabilities

- **Dynamic Spreadsheet Ingestion**: Upload `.csv` or `.xlsx` files directly in-chat. Binary safety validation inspects file structure, blocks macro-enabled workbooks, neutralizes formula injection, and handles irregular headers.
- **Schema Architect Agent**: Profiles column shapes, infers date formats, detects table grain, and proposes strongly typed schemas (`text`, `bigint`, `numeric`, `date`, `boolean`) with analytical roles (`measure`, `dimension`, `identifier`, `date`).
- **High-Speed Custom Tables**: Approved schemas are compiled into dynamic tables (`user_data.ds_*`) and populated using PostgreSQL streaming `COPY` in under 500ms.
- **Guarded SQL Agent (LangGraph)**: Translates natural language into single-statement read-only SELECT queries executed under a restricted PostgreSQL role (`nexus_reader`) enforced with Row-Level Security (`app.workspace_id`), statement timeouts (5s), and fetch limits.
- **Sandboxed Python Computation**: Calculations (growth rates, period-over-period differences, percentage shares, margins, ratios) run in an isolated subprocess (`run_python`) with AST import blocking and network restrictions.
- **Zero Mental Math Claim Verification**: A deterministic verification engine (`checker.py`) cross-references every numeric claim in an answer against the tool execution outputs of that specific turn. Unverified claims are flagged as caveats.
- **Full Audit Trace**: Every chat turn records its execution plan, SQL queries, row outputs, latency, and checker results in the PostgreSQL `runs` ledger.

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────┐
│                   Next.js 16 Client                    │
│   (TypeScript, Tailwind, shadcn/ui, JetBrains Mono)    │
└───────────────────────────┬────────────────────────────┘
                            │ SSE Stream / JSON APIs
┌───────────────────────────▼────────────────────────────┐
│                    FastAPI Backend                     │
├────────────────────────────┬───────────────────────────┤
│       Application CRUD     │      Agent & Execution    │
│      (SQLAlchemy 2.0)      │      (LangGraph Engine)   │
├────────────────────────────┼───────────────────────────┤
│ • Workspaces & Membership  │ • Schema Architect Agent  │
│ • Upload Ledger            │ • Nexus Copilot Agent     │
│ • Dataset & Column Catalog │ • AST Guard (sqlglot)     │
│ • Audit Runs & Feedback    │ • Python Sandbox (AST)    │
│                            │ • Number Checker          │
└────────────────────────────┴───────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│                  PostgreSQL Database                   │
├────────────────────────────┬───────────────────────────┤
│       public Schema        │     user_data Schema      │
│  (Catalog & Application)   │  (Dynamic Custom Tables)  │
├────────────────────────────┼───────────────────────────┤
│ • workspaces               │ • ds_<upload_id>          │
│ • uploads                  │ • ds_superstore           │
│ • datasets                 │                           │
│ • dataset_columns          ├───────────────────────────┤
│ • threads / runs           │   Row-Level Security:     │
│ • quarantine               │   nexus_reader (SELECT)   │
│ • users / members          │   nexus_writer (COPY/DDL) │
└────────────────────────────┴───────────────────────────┘
```

---

## Technology Stack

- **Frontend**: Next.js 16 (App Router), TypeScript, Tailwind CSS, shadcn/ui, Server-Sent Events (SSE).
- **Backend**: FastAPI, Pydantic v2, SQLAlchemy 2.0 (Hybrid ORM + Driver-level COPY).
- **Agent Framework**: LangGraph, LangChain Core.
- **Database**: PostgreSQL 16+ with Row-Level Security (RLS) and multi-schema separation.
- **SQL Analysis & Security**: sqlglot AST parsing and query rewriting.
- **Data Processing**: pandas, openpyxl.

---

## Repository Structure

```
.
├── backend/
│   ├── main.py                  # FastAPI application entry point
│   ├── utils.py                 # Central shared helpers (UUIDs, TSV escaping, formula safety)
│   ├── requirements.txt         # Production backend dependencies
│   ├── agent/
│   │   ├── nexus/               # Primary copilot agent (graph, checker, SQL and Python tools)
│   │   ├── architect/           # Schema Architect agent (column profiler, grain detection)
│   │   ├── db.py                # PostgreSQL connection runner (nexus_reader)
│   │   └── model.py             # LLM provider configuration
│   ├── api/
│   │   ├── routers/             # Domain endpoints (workspaces, uploads, runs, users, eval)
│   │   └── services/            # Domain logic (chat, workspace, upload, event streaming)
│   ├── db/
│   │   ├── session.py           # SQLAlchemy engine, session maker, connection pool
│   │   ├── models.py            # Declarative SQLAlchemy models
│   │   ├── changesets/          # Versioned SQL migrations (001 through 010)
│   │   └── seeds/               # Initial seed data loaders (load_superstore.py)
│   ├── ingest/
│   │   ├── reader.py            # File inspection, workbook parsing, header discovery
│   │   ├── custom_table.py      # DDL generation, dynamic COPY streaming, RLS policies
│   │   ├── pipeline.py          # Upload validation and architect routing
│   │   └── store.py             # Writer connection and raw query execution (nexus_writer)
│   ├── eval/
│   │   ├── golden_set.json      # 30 benchmark questions and ground-truth values
│   │   └── runner.py            # Automated evaluation runner
│   └── tests/                   # Consolidated pytest suite
├── frontend/
│   ├── app/                     # Next.js App Router pages and layouts
│   ├── components/              # Chat pane, schema architect card, audit bar, sidebar
│   ├── lib/                     # Global state, API client, SSE streaming store
│   └── public/                  # Static assets
└── context/                     # Architectural decision logs, design specs, and context index
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+ and npm
- PostgreSQL 16+ running locally or remotely

### 1. Database Setup

Create the database and configure user roles:

```sql
CREATE DATABASE nexus_db;
```

Run the changesets in order using `psql` or your database client:

```bash
# Windows PowerShell example
Get-ChildItem -Path backend/db/changesets/*.sql | Sort-Object Name | ForEach-Object {
    psql -U postgres -d nexus_db -f $_.FullName
}
```

Optional: Load the baseline Superstore benchmark dataset:

```bash
python backend/db/seeds/load_superstore.py
```

### 2. Backend Configuration

Create a `.env` file in the repository root:

```env
# Database Credentials
PGHOST=localhost
PGPORT=5432
PGDATABASE=nexus_db
PGUSER=postgres
PGPASSWORD=your_postgres_password
NEXUS_READER_PASSWORD=your_reader_password
NEXUS_WRITER_PASSWORD=your_writer_password

# LLM Provider Configuration
GROQ_API_KEY=your_groq_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
DEEPSEEK_API_KEY=your_deepseek_api_key
```

Install backend dependencies:

```bash
pip install -r backend/requirements.txt
```

Start the FastAPI application:

```bash
cd backend
uvicorn main:app --reload --port 8000
```

The API will be available at `http://127.0.0.1:8000`. Interactive docs are at `http://127.0.0.1:8000/docs`.

### 3. Frontend Setup

Navigate to the frontend directory and install dependencies:

```bash
cd frontend
npm install
```

Configure `frontend/.env.local` if using custom API host:

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

Start the development server:

```bash
npm run dev
```

Open `http://localhost:3000` in your browser.

---

## Verification & Testing

Run static compilation and type checks:

```bash
# Frontend typecheck
npm run typecheck --prefix frontend

# Backend test suite
pytest backend/tests

# Golden set evaluation benchmark (30 questions)
python backend/eval/runner.py
```

---

## Security & Operational Guardrails

- **Read-Only Database Role**: User queries execute under the unprivileged `nexus_reader` role. DDL and data modification statements (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`) are blocked both by PostgreSQL permissions and AST inspection.
- **Row-Level Security**: Every query is scoped to the workspace context via `SET LOCAL app.workspace_id = ...`.
- **Query Timeouts**: Queries timeout after 5 seconds to prevent runaway executions.
- **Execution Limits**: Preview outputs are capped at 25 rows for the model context and 200 rows for download exports.
- **Subprocess Isolation**: Python math execution occurs in an OS subprocess without network access and with a 10-second termination timeout.
- **Formula Injection Mitigation**: Exported CSVs escape formula triggers (`=`, `+`, `-`, `@`) with single quote prefixes.

