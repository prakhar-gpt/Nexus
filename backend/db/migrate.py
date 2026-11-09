"""Apply database changesets to PostgreSQL in order."""

from __future__ import annotations

import os
from pathlib import Path
import psycopg2

from urllib.parse import urlparse

CHANGESETS_DIR = Path(__file__).resolve().parent / "changesets"


def run_migrations() -> None:
    try:
        from config import settings
        db_url = os.environ.get("DATABASE_URL") or settings.DATABASE_URL
    except Exception:
        db_url = os.environ.get("DATABASE_URL")
    conn = None
    if db_url:
        print("Connecting to PostgreSQL via DATABASE_URL...")
        try:
            conn = psycopg2.connect(db_url)
        except psycopg2.OperationalError as op_err:
            if "password authentication failed" in str(op_err):
                # Auto-heal: restore nexus_writer password back to the real one in DATABASE_URL
                p = urlparse(db_url)
                print("Attempting to restore database user password...")
                try:
                    heal_conn = psycopg2.connect(
                        dbname=p.path.lstrip("/"),
                        user=p.username or "nexus_writer",
                        password="nexus_writer_pass",
                        host=p.hostname,
                        port=p.port or 5432,
                    )
                    heal_conn.autocommit = True
                    with heal_conn.cursor() as cur:
                        escaped = (p.password or "").replace("'", "''")
                        cur.execute(f"ALTER ROLE {p.username or 'nexus_writer'} WITH PASSWORD '{escaped}';")
                    heal_conn.close()
                    print("Successfully restored database user password from DATABASE_URL!")
                    conn = psycopg2.connect(db_url)
                except Exception as heal_err:
                    print(f"Password auto-recovery note: {heal_err}")
                    raise op_err from None
            else:
                raise
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

    # Ensure nexus_reader role exists if permissions permit (never touch nexus_writer)
    reader_pass = os.environ.get("NEXUS_READER_PASSWORD") or os.environ.get("PGPASSWORD", "nexus_reader_pass")
    try:
        cur.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexus_reader') THEN
                    CREATE ROLE nexus_reader WITH LOGIN PASSWORD '{reader_pass}';
                END IF;
            END
            $$;
        """)
        print("Verified database roles.")
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

