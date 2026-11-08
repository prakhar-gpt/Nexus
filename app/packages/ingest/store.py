"""Writes for the ingestion role. The password is read from the environment or .env."""

from __future__ import annotations

import csv
import io
import os
import psycopg2

from packages.agent.db import DATABASE, ENV_PATH, psql

WRITER_USER = "nexus_writer"


class StoreError(RuntimeError):
    pass


def writer_password() -> str:
    password = os.environ.get("NEXUS_WRITER_PASSWORD")
    if password:
        return password
    if not ENV_PATH.exists():
        raise StoreError("NEXUS_WRITER_PASSWORD is not set.")
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("NEXUS_WRITER_PASSWORD="):
            value = line.split("=", 1)[1].strip()
            if value:
                return value
    raise StoreError("NEXUS_WRITER_PASSWORD is not set.")


def get_writer_connection():
    """Return a psycopg2 connection authenticated as nexus_writer."""
    return psycopg2.connect(
        dbname=DATABASE,
        user=WRITER_USER,
        password=writer_password(),
        host="localhost",
        port=5432,
    )


def execute(sql: str) -> list[dict[str, str]]:
    try:
        output = psql(sql, user=WRITER_USER, password=writer_password(), database=DATABASE)
    except Exception as exc:
        raise StoreError(str(exc)) from exc
    if not output.strip():
        return []
    return list(csv.DictReader(io.StringIO(output)))


def sql_literal(value) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"
