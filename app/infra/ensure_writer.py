"""Create the nexus_writer role and apply Week 2 grants. Password stays in .env."""

from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app"))

from packages.agent.db import DATABASE, psql, _set_env_line  # noqa: E402

INFRA = Path(__file__).resolve().parent


def main() -> None:
    admin_password = os.environ.get("NEXUS_ADMIN_PASSWORD")
    if not admin_password:
        sys.exit("Set NEXUS_ADMIN_PASSWORD for this command only.")
    psql(
        (INFRA / "ingest_tables.sql").read_text(encoding="utf-8"),
        user="postgres",
        password=admin_password,
        database=DATABASE,
    )
    password = secrets.token_urlsafe(24)
    escaped = password.replace("'", "''")
    psql(
        "DO $$\n"
        "BEGIN\n"
        "  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexus_writer') THEN\n"
        f"    CREATE ROLE nexus_writer LOGIN PASSWORD '{escaped}';\n"
        "  ELSE\n"
        f"    ALTER ROLE nexus_writer PASSWORD '{escaped}';\n"
        "  END IF;\n"
        "END\n"
        "$$;",
        user="postgres",
        password=admin_password,
        database=DATABASE,
    )
    psql(
        (INFRA / "writer.sql").read_text(encoding="utf-8"),
        user="postgres",
        password=admin_password,
        database=DATABASE,
    )
    _set_env_line("NEXUS_WRITER_PASSWORD", password)
    print("writer ready")


if __name__ == "__main__":
    main()
