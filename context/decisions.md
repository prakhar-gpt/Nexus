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