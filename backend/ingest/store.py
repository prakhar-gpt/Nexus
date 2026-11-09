"""Writes for the ingestion role. The password is read from the environment or .env."""

from __future__ import annotations

import csv
import io
import os
import psycopg2

from agent.db import DATABASE, ENV_PATH, psql

WRITER_USER = "nexus_writer"


class StoreError(RuntimeError):
    pass


def writer_password() -> str:
    password = os.environ.get("NEXUS_WRITER_PASSWORD") or os.environ.get("PGPASSWORD")
    if password:
        return password
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if line.startswith("NEXUS_WRITER_PASSWORD="):
                value = line.split("=", 1)[1].strip()
                if value:
                    return value
    return "postgres"


def get_writer_connection():
    """Return a psycopg2 connection authenticated as nexus_writer."""
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        return psycopg2.connect(db_url)
    return psycopg2.connect(
        dbname=os.environ.get("PGDATABASE", DATABASE),
        user=os.environ.get("PGUSER", WRITER_USER),
        password=writer_password(),
        host=os.environ.get("PGHOST", "localhost"),
        port=int(os.environ.get("PGPORT", "5432")),
    )


def execute(sql: str) -> list[dict[str, str]]:
    """Execute SQL as writer using psycopg2 connection, or fallback to psql."""
    conn = None
    try:
        conn = get_writer_connection()
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql)
            if cur.description:
                columns = [col[0] for col in cur.description]
                rows = cur.fetchall()
                return [
                    dict(zip(columns, (str(val) if val is not None else "" for val in row)))
                    for row in rows
                ]
            return []
    except Exception as db_exc:
        try:
            output = psql(sql, user=WRITER_USER, password=writer_password(), database=DATABASE)
            if not output.strip():
                return []
            return list(csv.DictReader(io.StringIO(output)))
        except Exception:
            raise StoreError(str(db_exc)) from db_exc
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def sql_literal(value) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def sql_id(value) -> str:
    """Format any ID (UUID string, int, or uuid.UUID) safely for SQL queries."""
    if value is None:
        return "NULL"
    val_str = str(value).strip().replace("'", "''")
    return f"'{val_str}'"

