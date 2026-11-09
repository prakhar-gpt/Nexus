"""Apply database changesets to PostgreSQL in order."""

from __future__ import annotations

import os
from pathlib import Path
import psycopg2

CHANGESETS_DIR = Path(__file__).resolve().parent / "changesets"


def run_migrations() -> None:
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        print("Connecting to PostgreSQL via DATABASE_URL...")
        conn = psycopg2.connect(db_url)
    else:
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

    # Ensure nexus_reader and nexus_writer roles exist if permissions permit
    reader_pass = os.environ.get("NEXUS_READER_PASSWORD") or os.environ.get("PGPASSWORD", "nexus_reader_pass")
    writer_pass = os.environ.get("NEXUS_WRITER_PASSWORD") or os.environ.get("PGPASSWORD", "nexus_writer_pass")
    try:
        cur.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexus_reader') THEN
                    CREATE ROLE nexus_reader WITH LOGIN PASSWORD '{reader_pass}';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexus_writer') THEN
                    CREATE ROLE nexus_writer WITH LOGIN PASSWORD '{writer_pass}';
                END IF;
            END
            $$;
        """)
        print("Verified nexus_reader and nexus_writer roles.")
    except Exception as exc:
        print(f"Role creation check note: {exc}")

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

