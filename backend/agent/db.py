"""Connections for the read-only SQL tool. Passwords stay in the environment or .env."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / ".env"
PSQL = Path(r"C:\Program Files\PostgreSQL\18\bin\psql.exe")
READER_USER = "nexus_reader"
DATABASE = "nexus_db"
READER_SQL = Path(__file__).resolve().parents[1] / "db" / "changesets" / "reader.sql"

_ENV_KEYS = ("NEXUS_READER_PASSWORD",)


class DatabaseError(RuntimeError):
    pass


def reader_password() -> str:
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


def psql(sql: str, *, user: str, password: str, database: str) -> str:
    if not PSQL.exists():
        raise DatabaseError(f"psql not found at {PSQL}")
    env = {
        "PATH": os.environ.get("PATH", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "PGCLIENTENCODING": "UTF8",
        "PGHOST": "localhost",
        "PGPORT": "5432",
        "PGUSER": user,
        "PGPASSWORD": password,
        "PGDATABASE": database,
    }
    result = subprocess.run(
        [str(PSQL), "-w", "-v", "ON_ERROR_STOP=1", "-X", "-q", "--csv", "-d", database],
        input=sql,
        text=True,
        encoding="utf-8",
        capture_output=True,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or "psql failed"
        raise DatabaseError(message)
    return result.stdout


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
