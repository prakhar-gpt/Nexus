"""Create nexus_db, apply schema.sql, and load datasets/Superstore/Superstore.csv.

Uses the existing local Postgres. Connection comes from the environment:
  PGHOST (default localhost), PGPORT (default 5432), PGUSER (default postgres),
  PGPASSWORD (required). The password is never written to disk.
"""

from __future__ import annotations

import csv
import hashlib
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = ROOT / "datasets" / "Superstore" / "Superstore.csv"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
PSQL = Path(r"C:\Program Files\PostgreSQL\18\bin\psql.exe")
DATABASE = "nexus_db"

COPY_COLUMNS = (
    "workspace_id",
    "upload_id",
    "order_date",
    "customer_id",
    "product_id",
    "quantity",
    "revenue",
    "unit_price",
    "discount_pct",
    "cost",
    "profit",
    "segment",
    "region",
    "category",
    "sub_category",
    "channel",
)


def psql(database: str, *args: str, input_text: str | None = None) -> str:
    if not PSQL.exists():
        sys.exit(f"psql not found at {PSQL}")
    if not os.environ.get("PGPASSWORD"):
        sys.exit("Set PGPASSWORD for the local postgres role. It is not stored in the repo.")
    env = os.environ.copy()
    env.setdefault("PGHOST", "localhost")
    env.setdefault("PGPORT", "5432")
    env.setdefault("PGUSER", "postgres")
    command = [
        str(PSQL),
        "-w",
        "-v",
        "ON_ERROR_STOP=1",
        "-X",
        "-d",
        database,
        *args,
    ]
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        sys.exit(result.returncode)
    return result.stdout.strip()


def ensure_database() -> None:
    exists = psql(
        "postgres",
        "-tAc",
        "SELECT 1 FROM pg_database WHERE datname = 'nexus_db'",
    )
    if exists != "1":
        psql("postgres", "-c", "CREATE DATABASE nexus_db")


def file_fingerprint() -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with CSV_PATH.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def seed_ids(sha256: str, size: int) -> tuple[str, str] | None:
    existing = psql(
        DATABASE,
        "-tAc",
        "SELECT id FROM uploads WHERE sha256 = "
        f"'{sha256}'",
    )
    if existing:
        return None
    workspace_id = psql(
        DATABASE,
        "-tAc",
        "SELECT id FROM workspaces WHERE name = 'Superstore' ORDER BY id LIMIT 1",
    )
    if not workspace_id:
        workspace_id = psql(
            DATABASE,
            "-tAc",
            "INSERT INTO workspaces (name) VALUES ('Superstore') RETURNING id",
        )
    stored_name = f"seed-{sha256[:12]}.csv"
    upload_id = psql(
        DATABASE,
        "-tAc",
        "INSERT INTO uploads "
        "(workspace_id, original_name, stored_name, sha256, size, status) "
        "VALUES "
        f"({workspace_id}, 'Superstore.csv', '{stored_name}', '{sha256}', {size}, 'loaded') "
        "RETURNING id",
    )
    return workspace_id, upload_id


def write_load_csv(destination: Path, workspace_id: str, upload_id: str) -> int:
    count = 0
    with CSV_PATH.open(newline="", encoding="utf-8-sig") as source, destination.open(
        "w", newline="", encoding="utf-8"
    ) as target:
        reader = csv.DictReader(source)
        writer = csv.DictWriter(target, fieldnames=COPY_COLUMNS)
        writer.writeheader()
        for row in reader:
            order_date = datetime.strptime(row["Order Date"].strip(), "%d/%m/%Y").date()
            writer.writerow(
                {
                    "workspace_id": workspace_id,
                    "upload_id": upload_id,
                    "order_date": order_date.isoformat(),
                    "customer_id": row["Customer ID"].strip(),
                    "product_id": row["Product ID"].strip(),
                    "quantity": "",
                    "revenue": row["Sales"].strip(),
                    "unit_price": "",
                    "discount_pct": "",
                    "cost": "",
                    "profit": "",
                    "segment": row["Segment"].strip(),
                    "region": row["Region"].strip(),
                    "category": row["Category"].strip(),
                    "sub_category": row["Sub-Category"].strip(),
                    "channel": "",
                }
            )
            count += 1
    return count


def copy_csv(csv_path: Path) -> None:
    column_list = ", ".join(COPY_COLUMNS)
    copy_path = csv_path.as_posix()
    script = (
        f"\\copy sales_clean ({column_list}) "
        f"FROM '{copy_path}' WITH (FORMAT csv, HEADER true)\n"
    )
    psql(DATABASE, "-f", "-", input_text=script)


def main() -> None:
    if not CSV_PATH.exists():
        sys.exit(f"Missing dataset: {CSV_PATH}")
    ensure_database()
    psql(DATABASE, "-f", str(SCHEMA_PATH))
    sha256, size = file_fingerprint()
    ids = seed_ids(sha256, size)
    if ids is None:
        loaded = psql(DATABASE, "-tAc", "SELECT count(*) FROM sales_clean")
        print(f"Already loaded sha256 {sha256}. sales_clean rows: {loaded}")
        return
    workspace_id, upload_id = ids
    with tempfile.TemporaryDirectory() as temporary:
        staged = Path(temporary) / "sales_clean.csv"
        count = write_load_csv(staged, workspace_id, upload_id)
        copy_csv(staged)
    loaded = psql(DATABASE, "-tAc", "SELECT count(*) FROM sales_clean")
    print(
        f"Loaded {count} rows into nexus_db.sales_clean "
        f"(workspace {workspace_id}, upload {upload_id}). "
        f"Table count: {loaded}."
    )


if __name__ == "__main__":
    main()
