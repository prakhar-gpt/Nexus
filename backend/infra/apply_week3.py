"""Apply week3.sql with the postgres role. The password comes from the environment."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app"))

from agent.db import DATABASE, psql  # noqa: E402

PASSWORD_KEY = "NEXUS_ADMIN_PASSWORD"


def main() -> int:
    password = os.environ.get(PASSWORD_KEY, "")
    if not password:
        print(f"{PASSWORD_KEY} is not set.", file=sys.stderr)
        return 1
    sql = (Path(__file__).resolve().parent / "week3.sql").read_text(encoding="utf-8")
    psql(sql, user="postgres", password=password, database=DATABASE)
    print("week 3 schema applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
