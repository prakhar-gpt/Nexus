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
            os.environ.setdefault("PGHOST", parsed.hostname)
        if parsed.port:
            os.environ.setdefault("PGPORT", str(parsed.port))
        if parsed.username:
            os.environ.setdefault("PGUSER", parsed.username)
            os.environ.setdefault("PG_READER_USER", parsed.username)
        if parsed.password:
            os.environ.setdefault("PGPASSWORD", parsed.password)
            os.environ.setdefault("NEXUS_WRITER_PASSWORD", parsed.password)
            os.environ.setdefault("NEXUS_READER_PASSWORD", parsed.password)
        if parsed.path and len(parsed.path) > 1:
            os.environ.setdefault("PGDATABASE", parsed.path.lstrip("/"))
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

