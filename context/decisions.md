# Architectural Decisions (ADRs)

* **Decision 1:** Use RapidFuzz for column mapping instead of an LLM.
  * *Reason:* Sub-millisecond latency, zero cost, and highly deterministic for standard retail headers. LLMs are reserved strictly for fallback on ambiguous columns.
* **Decision 2:** Single LangGraph loop instead of a multi-agent system.
  * *Reason:* Reduces latency and compounding error rates. Complexity must be justified by measured eval failures.
* **Decision 3:** Ingestion runs via FastAPI Background Tasks.
  * *Reason:* Eliminates the need for Celery/Redis infrastructure in the MVP.
* **Decision 4:** Audit via Python Checker, not an Audit Agent.
  * *Reason:* LLMs hallucinating verifications of other LLMs is unreliable. Regex + SQL JSON cross-referencing guarantees mathematical fidelity.
* **Decision 5 (2026-11-08):** Week 1 uses the existing local PostgreSQL and pgAdmin. Do not add a Docker Postgres service.
  * *Reason:* Postgres and pgAdmin are already installed.
  * *Rejected:* `pgvector/pgvector:pg15` via `app/infra/docker-compose.yml`.
  * *Files affected:* none yet. No DDL has been applied.

Decisions 6–13 were incorporated from the v2 product document on 2026-11-08. The resulting design is in `architecture.md`.

* **Decision 6 (2026-11-08):** Clean Postgres tables are the source of truth at question time. Keep the raw file for lineage and debugging.
  * *Rejected:* Re-reading the upload to answer a question.
* **Decision 7 (2026-11-08):** pgvector runs in the same Postgres as the tables.
  * *Rejected:* A separate vector database. Azure AI Search remains a later swap.
* **Decision 8 (2026-11-08):** The knowledge base is markdown in the repo.
  * *Rejected for v1:* Neo4j. It is an add-on only.
* **Decision 9 (2026-11-08):** v1 retrieval is pgvector semantic search plus a metadata filter.
  * *Rejected for v1:* Hybrid BM25 and a cross-encoder reranker.
* **Decision 10 (2026-11-08):** Web search is off by default. A run that uses it must be labelled external.
* **Decision 11 (2026-11-08):** Streams use server-sent events.
* **Decision 12 (2026-11-08):** The UI is one dashboard with three panes.
  * *Rejected:* A nine-screen app and multi-page routing.
* **Decision 13 (2026-11-08):** v1 accepts one canonical sales shape plus optional documents.
  * *Rejected:* Chat with any file. Payroll, wide pivots, and free-form reports are out of scope.