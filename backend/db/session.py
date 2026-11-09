"""SQLAlchemy database engine and session management for Nexus."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator
from urllib.parse import urlparse

from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / ".env"

raw_db_url = os.environ.get("DATABASE_URL")
if raw_db_url:
    try:
        parsed = urlparse(raw_db_url)
        if parsed.hostname:
            os.environ["PGHOST"] = parsed.hostname
        if parsed.port:
            os.environ["PGPORT"] = str(parsed.port)
        if parsed.username:
            os.environ["PGUSER"] = parsed.username
            os.environ["PG_READER_USER"] = parsed.username
        if parsed.password:
            os.environ["PGPASSWORD"] = parsed.password
            os.environ["NEXUS_WRITER_PASSWORD"] = parsed.password
            os.environ["NEXUS_READER_PASSWORD"] = parsed.password
        if parsed.path and len(parsed.path) > 1:
            os.environ["PGDATABASE"] = parsed.path.lstrip("/")

        # Self-healing check: if password was inadvertently altered, restore it from DATABASE_URL
        if parsed.password:
            import psycopg2
            try:
                test_c = psycopg2.connect(raw_db_url, connect_timeout=3)
                test_c.close()
            except psycopg2.OperationalError as op_err:
                if "password authentication failed" in str(op_err):
                    heal_c = psycopg2.connect(
                        dbname=parsed.path.lstrip("/"),
                        user=parsed.username or "nexus_writer",
                        password="nexus_writer_pass",
                        host=parsed.hostname,
                        port=parsed.port or 5432,
                        connect_timeout=3,
                    )
                    heal_c.autocommit = True
                    with heal_c.cursor() as cur:
                        escaped = parsed.password.replace("'", "''")
                        cur.execute(f"ALTER ROLE {parsed.username or 'nexus_writer'} WITH PASSWORD '{escaped}';")
                    heal_c.close()
    except Exception:
        pass

    if raw_db_url.startswith("postgres://"):
        DATABASE_URL = raw_db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif raw_db_url.startswith("postgresql://") and not raw_db_url.startswith("postgresql+"):
        DATABASE_URL = raw_db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    else:
        DATABASE_URL = raw_db_url
else:
    DATABASE = os.environ.get("PGDATABASE", "nexus_db")
    WRITER_USER = os.environ.get("PGUSER", "nexus_writer")
    HOST = os.environ.get("PGHOST", "localhost")
    PORT = os.environ.get("PGPORT", "5432")

    def _get_writer_password() -> str:
        try:
            from config import settings
            if settings.NEXUS_WRITER_PASSWORD:
                return settings.NEXUS_WRITER_PASSWORD
        except Exception:
            pass
        password = os.environ.get("NEXUS_WRITER_PASSWORD") or os.environ.get("PGPASSWORD")
        if password:
            return password
        if ENV_PATH.exists():
            for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
                if line.startswith("NEXUS_WRITER_PASSWORD="):
                    val = line.split("=", 1)[1].strip()
                    if val:
                        return val
        return "postgres"

    DATABASE_URL = (
        f"postgresql+psycopg2://{WRITER_USER}:{_get_writer_password()}@{HOST}:{PORT}/{DATABASE}"
    )

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding an isolated SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Context manager for transactional operations with automatic commit/rollback."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

