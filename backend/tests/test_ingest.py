"""The six Week 2 files, plus row quarantine and a macro workbook."""

from __future__ import annotations

import io
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from agent.nexus.tools import run_sql  # noqa: E402
from ingest.pipeline import ingest  # noqa: E402
from ingest.store import execute  # noqa: E402

FIXTURES = ROOT / "datasets" / "tests"
FAILURES = []


def workspace_id() -> str:
    found = execute(
        "SELECT id FROM workspaces WHERE name = 'Week 2 tests' ORDER BY id LIMIT 1"
    )
    if found:
        return str(found[0]["id"])
    created = execute("INSERT INTO workspaces (name) VALUES ('Week 2 tests') RETURNING id")
    return str(created[0]["id"])


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("pass" if ok else "FAIL"), name, detail)
    if not ok:
        FAILURES.append(name)


def accept_all(pending):
    return {item.source: item.canonical for item in pending}


def main() -> int:
    room = workspace_id()
    execute(f"DELETE FROM sales_clean WHERE workspace_id = {room}")
    execute(f"DELETE FROM quarantine WHERE upload_id IN (SELECT id FROM uploads WHERE workspace_id = {room})")
    execute(f"DELETE FROM column_mapping WHERE upload_id IN (SELECT id FROM uploads WHERE workspace_id = {room})")
    execute(f"DELETE FROM uploads WHERE workspace_id = {room}")

    clean = ingest(FIXTURES / "01_clean.csv", room)
    check(
        "1 clean sales table",
        clean.status == "accepted"
        and clean.loaded_rows == 2
        and clean.quarantined_rows == 0
        and all(item.method == "fuzzy" and not item.needs_confirmation for item in clean.mappings if item.canonical),
        clean.status,
    )

    junk = ingest(FIXTURES / "02_junk_header.csv", room)
    junk_date = execute(
        f"SET app.workspace_id = '{room}'; "
        "SELECT order_date::text AS order_date FROM sales_clean "
        f"WHERE upload_id = {junk.upload_id}"
    )
    check(
        "2 junk rows above the header",
        junk.status == "accepted" and junk.header_line == 3 and junk_date == [{"order_date": "2024-08-15"}],
        f"line={junk.header_line} date={junk_date} status={junk.status}",
    )

    waiting = ingest(FIXTURES / "03_messy.csv", room)
    confirmed = ingest(FIXTURES / "03_messy.csv", room, confirm=accept_all)
    loaded = execute(
        f"SET app.workspace_id = '{room}'; "
        "SELECT order_date::text AS order_date, revenue::text AS revenue "
        f"FROM sales_clean WHERE upload_id = {confirmed.upload_id}"
    )
    methods = {item.source: item.method for item in confirmed.mappings}
    check(
        "3 messy names and text numbers",
        waiting.status == "needs_confirmation"
        and waiting.loaded_rows == 0
        and confirmed.status == "accepted"
        and loaded == [{"order_date": "2024-04-01", "revenue": "1200.50"}]
        and methods.get("Rev $") == "llm"
        and methods.get("Order Dt") == "fuzzy",
        f"wait={waiting.status} loaded={loaded} methods={methods}",
    )

    single = ingest(FIXTURES / "04_single_column.csv", room)
    empty_path = Path(tempfile.gettempdir()) / "nexus_empty.csv"
    empty_path.write_bytes(b"")
    empty = ingest(empty_path, room)
    check(
        "4 empty or single-column file",
        single.status == "rejected"
        and "single-column" in (single.reason or "")
        and empty.status == "rejected"
        and empty.reason == "empty file",
        f"single={single.reason} empty={empty.reason}",
    )

    payroll = ingest(FIXTURES / "05_payroll.csv", room)
    check(
        "5 unrelated data (payroll)",
        payroll.status == "rejected" and "missing" in (payroll.reason or ""),
        payroll.reason,
    )

    injection = ingest(FIXTURES / "06_injection.csv", room)
    visible = run_sql(
        "SELECT segment, category FROM sales_clean "
        f"WHERE upload_id = {injection.upload_id}",
        room,
    )
    check(
        "6 formula-like and prompt-injection text",
        injection.status == "accepted"
        and injection.quarantined_rows == 0
        and visible
        and visible[0]["segment"].startswith("'=")
        and "Ignore previous instructions" in visible[0]["category"],
        f"status={injection.status} visible={visible}",
    )

    rules_path = Path(tempfile.gettempdir()) / "nexus_row_rules.csv"
    rules_path.write_text(
        "Order Date,Customer ID,Product ID,Revenue,Segment,Region,Category,Sub-Category\n"
        "2024-01-01,C-1,P-1,10,Consumer,West,Furniture,Chairs\n"
        "2024-01-01,C-1,P-1,10,Consumer,West,Furniture,Chairs\n"
        "not-a-date,C-2,P-2,5,Consumer,West,Furniture,Chairs\n"
        "2024-01-03,C-3,P-3,-4,Consumer,West,Furniture,Chairs\n",
        encoding="utf-8",
    )
    rules = ingest(rules_path, room)
    reasons = {
        row["reason"]
        for row in execute(
            f"SELECT reason FROM quarantine WHERE upload_id = {rules.upload_id}"
        )
    }
    check(
        "row quarantine",
        rules.loaded_rows == 1
        and rules.quarantined_rows == 3
        and reasons == {"duplicate", "invalid date", "negative revenue"},
        f"loaded={rules.loaded_rows} reasons={reasons}",
    )

    macro_path = Path(tempfile.gettempdir()) / "nexus_macro.xlsx"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("xl/vbaProject.bin", b"macro")
        archive.writestr("[Content_Types].xml", "<Types></Types>")
    macro_path.write_bytes(buffer.getvalue())
    macro = ingest(macro_path, room)
    check(
        "macro workbook",
        macro.status == "rejected" and "macro" in (macro.reason or ""),
        macro.reason,
    )

    print(f"failures={len(FAILURES)}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())


def test_ingest_pipeline():
    assert main() == 0
