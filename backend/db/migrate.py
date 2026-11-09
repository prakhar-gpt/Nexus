"""Apply database changesets to PostgreSQL in order."""

from __future__ import annotations

import os
from pathlib import Path
import psycopg2

CHANGESETS_DIR = Path(__file__).resolve().parent / "changesets"


def run_migrations() -> None:
    host = os.environ.get("PGHOST", "localhost")
    port = int(os.environ.get("PGPORT", "5432"))
    dbname = os.environ.get("PGDATABASE", "nexus_db")
    user = os.environ.get("PGUSER", "postgres")
    password = os.environ.get("NEXUS_WRITER_PASSWORD") or os.environ.get("PGPASSWORD", "postgres")

    print(f"Connecting to {dbname} on {host}:{port} as {user}...")
    conn = psycopg2.connect(
        dbname=dbname,
        user=user,
        password=password,
        host=host,
        port=port,
    )
    conn.autocommit = True
    cur = conn.cursor()

    # Ensure user_data schema exists
    cur.execute("CREATE SCHEMA IF NOT EXISTS user_data;")

    # Track applied migrations
    cur.execute("""
        CREATE TABLE IF NOT EXISTS public.schema_migrations (
            version VARCHAR(255) PRIMARY KEY,
            applied_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 1. Apply numbered changesets in order
    numbered_files = sorted([f for f in CHANGESETS_DIR.glob("*.sql") if f.name[:3].isdigit()])
    for file in numbered_files:
        version = file.name
        cur.execute("SELECT 1 FROM public.schema_migrations WHERE version = %s;", (version,))
        if cur.fetchone():
            print(f"Skipping {version} (already applied)")
            continue

        print(f"Applying {version}...")
        sql = file.read_text(encoding="utf-8")
        cur.execute(sql)
        cur.execute("INSERT INTO public.schema_migrations (version) VALUES (%s);", (version,))
        print(f"Successfully applied {version}")

    cur.close()
    conn.close()
    print("Database migrations completed successfully.")


if __name__ == "__main__":
    run_migrations()
