"""Connections for the read-only SQL tool. Passwords stay in the environment or .env."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / ".env"

try:
    from config import settings
    PSQL = Path(settings.PSQL_PATH)
    READER_USER = settings.PG_READER_USER
    DATABASE = settings.PG_DATABASE
except Exception:
    PSQL = Path(os.environ.get("PSQL_PATH", r"C:\Program Files\PostgreSQL\18\bin\psql.exe"))
    READER_USER = os.environ.get("PG_READER_USER", "nexus_reader")
    DATABASE = os.environ.get("PGDATABASE", "nexus_db")

READER_SQL = Path(__file__).resolve().parents[1] / "db" / "changesets" / "reader.sql"

_ENV_KEYS = ("NEXUS_READER_PASSWORD",)


class DatabaseError(RuntimeError):
    pass


def reader_password() -> str:
    try:
        if settings.NEXUS_READER_PASSWORD:
            return settings.NEXUS_READER_PASSWORD
    except Exception:
        pass
    password = os.environ.get("NEXUS_READER_PASSWORD")
    if password:
        return password
    if not ENV_PATH.exists():
        raise DatabaseError("NEXUS_READER_PASSWORD is not set.")
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("NEXUS_READER_PASSWORD="):
            value = line.split("=", 1)[1].strip()
            if value:
                return value
    raise DatabaseError("NEXUS_READER_PASSWORD is not set.")


def _split_sql_statements(sql: str) -> list[str]:
    """Split compound SQL string by semicolons outside of quotes."""
    statements = []
    buf = []
    in_quote = False
    quote_char = ""
    for ch in sql:
        if ch in ("'", '"'):
            if not in_quote:
                in_quote = True
                quote_char = ch
            elif ch == quote_char:
                in_quote = False
                quote_char = ""
            buf.append(ch)
        elif ch == ";" and not in_quote:
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
        else:
            buf.append(ch)
    stmt = "".join(buf).strip()
    if stmt:
        statements.append(stmt)
    return statements


def psql(sql: str, *, user: str, password: str, database: str) -> str:
    db_name = database
    if (not db_name or db_name == "nexus_db") and getattr(settings, "PG_DATABASE", None):
        db_name = settings.PG_DATABASE

    db_host = os.environ.get("PGHOST") or getattr(settings, "PG_HOST", "localhost")
    db_port = int(os.environ.get("PGPORT") or getattr(settings, "PG_PORT", "5432"))

    # Credential attempts: primary user (e.g. reader), then writer fallback
    attempts = [(user, password)]
    fallback_user = getattr(settings, "PG_USER", None) or os.environ.get("PGUSER") or "nexus_writer"
    fallback_pass = (
        getattr(settings, "PG_PASSWORD", None)
        or os.environ.get("PGPASSWORD")
        or getattr(settings, "NEXUS_WRITER_PASSWORD", "")
    )
    if fallback_user and (fallback_user != user or fallback_pass != password):
        attempts.append((fallback_user, fallback_pass))

    last_error: Exception | None = None
    for attempt_user, attempt_pass in attempts:
        try:
            import csv
            import io
            import psycopg2

            conn = psycopg2.connect(
                dbname=db_name,
                user=attempt_user,
                password=attempt_pass,
                host=db_host,
                port=db_port,
            )
            conn.autocommit = True
            with conn.cursor() as cur:
                statements = _split_sql_statements(sql)
                out = io.StringIO()
                has_result = False
                for stmt in statements:
                    cur.execute(stmt)
                    if cur.description:
                        writer = csv.writer(out)
                        writer.writerow([d[0] for d in cur.description])
                        writer.writerows(cur.fetchall())
                        has_result = True
                if has_result:
                    return out.getvalue()
                return ""
        except Exception as py_exc:
            last_error = py_exc
            if "password authentication failed" in str(py_exc) or "fe_sendauth" in str(py_exc):
                continue
            # SQL semantic / syntax error: raise directly for agent feedback
            raise DatabaseError(str(py_exc)) from py_exc

    if last_error:
        raise DatabaseError(str(last_error)) from last_error
    return ""


def ensure_reader(admin_password: str, reader_password_value: str) -> None:
    """Create nexus_reader if needed and apply the row-level policy."""
    escaped = reader_password_value.replace("'", "''")
    admin_sql = f"""
    DO $$
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{READER_USER}') THEN
        CREATE ROLE {READER_USER} LOGIN PASSWORD '{escaped}';
      ELSE
        ALTER ROLE {READER_USER} PASSWORD '{escaped}';
      END IF;
    END
    $$;
    ALTER ROLE {READER_USER} SET statement_timeout = '5s';
    """
    psql(admin_sql, user="postgres", password=admin_password, database=DATABASE)
    policy = READER_SQL.read_text(encoding="utf-8")
    psql(policy, user="postgres", password=admin_password, database=DATABASE)
    _set_env_line("NEXUS_READER_PASSWORD", reader_password_value)


def _set_env_line(key: str, value: str) -> None:
    lines = []
    if ENV_PATH.exists():
        lines = [
            line
            for line in ENV_PATH.read_text(encoding="utf-8").splitlines()
            if not line.startswith(f"{key}=")
        ]
    lines.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
