"""Reset and truncate all dynamic Nexus database tables and uploads."""

from __future__ import annotations

import os
import psycopg2
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = ROOT / "datasets" / "uploads"
DATABASE = "nexus_db"


def reset_database() -> None:
    password = os.environ.get("PGPASSWORD", "postgres")
    user = os.environ.get("PGUSER", "postgres")
    host = os.environ.get("PGHOST", "localhost")
    port = int(os.environ.get("PGPORT", "5432"))

    conn = psycopg2.connect(
        dbname=DATABASE,
        user=user,
        password=password,
        host=host,
        port=port,
    )
    conn.autocommit = True
    cur = conn.cursor()

    # 1. Drop dynamic custom tables in user_data
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'user_data' AND table_name != 'ds_superstore'
    """)
    custom_tables = cur.fetchall()
    for (t,) in custom_tables:
        cur.execute(f'DROP TABLE IF EXISTS user_data."{t}" CASCADE;')
        print(f"Dropped user_data.{t}")

    # 2. Truncate user_data.ds_superstore (keeps sales_clean view valid)
    cur.execute("TRUNCATE TABLE user_data.ds_superstore RESTART IDENTITY CASCADE;")
    print("Truncated user_data.ds_superstore")

    # 3. Truncate all public base tables
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
    """)
    public_tables = [row[0] for row in cur.fetchall()]
    for t in public_tables:
        cur.execute(f'TRUNCATE TABLE public."{t}" RESTART IDENTITY CASCADE;')
        print(f"Truncated public.{t}")

    # Re-seed default user if users table exists
    cur.execute("""
        SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'users'
    """)
    if cur.fetchone():
        cur.execute("""
            INSERT INTO users (id, email, name, role)
            VALUES ('00000000-0000-0000-0000-000000000001'::uuid, 'prakhar@nexus.ai', 'Prakhar Gupta', 'Consulting Analyst')
            ON CONFLICT (email) DO NOTHING;
        """)
        print("Re-seeded default user (00000000-0000-0000-0000-000000000001)")

    # 4. Clean uploads cache
    removed_files = 0
    if UPLOAD_DIR.exists():
        for f in UPLOAD_DIR.iterdir():
            if f.is_file():
                f.unlink()
                removed_files += 1
    print(f"Removed {removed_files} cached files from {UPLOAD_DIR}")

    # 5. Verification
    print("\n--- Verification ---")
    for t in public_tables:
        cur.execute(f'SELECT count(*) FROM public."{t}"')
        cnt = cur.fetchone()[0]
        print(f"public.{t}: {cnt} rows")

    cur.execute("SELECT count(*) FROM user_data.ds_superstore")
    cnt_super = cur.fetchone()[0]
    print(f"user_data.ds_superstore: {cnt_super} rows")

    cur.execute("""
        SELECT count(*) 
        FROM information_schema.tables 
        WHERE table_schema = 'user_data' AND table_name != 'ds_superstore'
    """)
    cnt_custom = cur.fetchone()[0]
    print(f"user_data custom tables remaining: {cnt_custom}")

    cur.close()
    conn.close()
    print("\nNexus DBs wiped clean!")


if __name__ == "__main__":
    reset_database()
