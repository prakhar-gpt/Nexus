"""Turn one spreadsheet into sales_clean rows, or reject it with a reason."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from packages.ingest.clean import make_inert, parse_date, parse_number
from packages.ingest.mapping import (
    CANONICAL,
    Proposal,
    domain_gap,
    propose_columns,
)
from packages.ingest.safety import RejectedFile, inspect, stored_name
from packages.ingest.store import execute, sql_literal
from packages.ingest.tables import TableRejected, find_header, read_rows

ROOT = Path(__file__).resolve().parents[3]
UPLOAD_DIR = ROOT / "datasets" / "uploads"
TEXT_COLUMNS = (
    "customer_id",
    "product_id",
    "segment",
    "region",
    "category",
    "sub_category",
    "channel",
)
NUMBER_COLUMNS = ("revenue", "unit_price", "discount_pct", "cost", "profit", "quantity")


@dataclass
class IngestResult:
    status: str
    reason: str | None = None
    upload_id: int | None = None
    stored_name: str | None = None
    header_line: int | None = None
    loaded_rows: int = 0
    quarantined_rows: int = 0
    mappings: list[Proposal] = field(default_factory=list)


def ingest(path: Path, workspace_id: int, confirm=None) -> IngestResult:
    path = Path(path)
    try:
        data, extension = inspect(path)
    except RejectedFile as exc:
        upload_id, name = _record_upload(path, workspace_id, "rejected", path.read_bytes() if path.is_file() else b"")
        return IngestResult("rejected", exc.reason, upload_id, name)

    try:
        rows = read_rows(path, extension)
    except TableRejected as exc:
        upload_id, name = _record_upload(path, workspace_id, "rejected", data)
        return IngestResult("rejected", exc.reason, upload_id, name)

    header_line, headers = find_header(rows)
    if header_line is None:
        upload_id, name = _record_upload(path, workspace_id, "rejected", data)
        return IngestResult("rejected", "could not find a header row", upload_id, name)

    proposals = propose_columns(headers)
    pending = [item for item in proposals if item.needs_confirmation]
    if pending and confirm is None:
        if domain_gap(_accepted_columns(proposals, include_pending=True)):
            reason = domain_gap(_accepted_columns(proposals, include_pending=True))
            upload_id, name = _record_upload(path, workspace_id, "rejected", data)
            _save_mappings(upload_id, proposals)
            return IngestResult("rejected", reason, upload_id, name, header_line, mappings=proposals)
        upload_id, name = _record_upload(path, workspace_id, "needs_confirmation", data)
        _save_mappings(upload_id, proposals)
        return IngestResult(
            "needs_confirmation",
            "confirm the low-confidence columns before loading rows",
            upload_id,
            name,
            header_line,
            mappings=proposals,
        )
    if confirm is not None:
        decisions = confirm(pending)
        for proposal in pending:
            if proposal.source not in decisions:
                continue
            proposal.canonical = decisions[proposal.source]
            proposal.needs_confirmation = False
            proposal.confirmed_by_user = True

    columns = _accepted_columns(proposals, include_pending=False)
    gap = domain_gap(columns)
    if gap:
        upload_id, name = _record_upload(path, workspace_id, "rejected", data)
        _save_mappings(upload_id, proposals)
        return IngestResult("rejected", gap, upload_id, name, header_line, mappings=proposals)

    upload_id, name = _record_upload(path, workspace_id, "accepted", data)
    _save_mappings(upload_id, proposals)
    loaded, quarantined = _load_rows(upload_id, workspace_id, rows, header_line, proposals)
    return IngestResult(
        "accepted",
        None,
        upload_id,
        name,
        header_line,
        loaded,
        quarantined,
        proposals,
    )


def _accepted_columns(proposals: list[Proposal], include_pending: bool) -> set[str]:
    columns = set()
    for proposal in proposals:
        if not proposal.canonical:
            continue
        if proposal.needs_confirmation and not include_pending:
            continue
        columns.add(proposal.canonical)
    return columns


def _record_upload(path: Path, workspace_id: int, status: str, data: bytes) -> tuple[int, str]:
    digest = hashlib.sha256(data).hexdigest()
    extension = path.suffix.lower() if path.suffix else ".csv"
    name = stored_name(digest, extension if extension in {".csv", ".xlsx"} else ".bin")
    if data:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        (UPLOAD_DIR / name).write_bytes(data)
    rows = execute(
        "INSERT INTO uploads "
        "(workspace_id, original_name, stored_name, sha256, size, status) "
        f"VALUES ({int(workspace_id)}, {sql_literal(path.name)}, {sql_literal(name)}, "
        f"{sql_literal(digest)}, {len(data)}, {sql_literal(status)}) "
        "RETURNING id"
    )
    return int(rows[0]["id"]), name


def _save_mappings(upload_id: int, proposals: list[Proposal]) -> None:
    for proposal in proposals:
        execute(
            "INSERT INTO column_mapping "
            "(upload_id, source_column, canonical_column, confidence, method, confirmed_by_user) "
            f"VALUES ({upload_id}, {sql_literal(proposal.source)}, "
            f"{sql_literal(proposal.canonical)}, {proposal.confidence}, "
            f"{sql_literal(proposal.method)}, "
            f"{'true' if proposal.confirmed_by_user else 'false'})"
        )


def _load_rows(upload_id, workspace_id, rows, header_line, proposals) -> tuple[int, int]:
    by_source = {proposal.source: proposal for proposal in proposals}
    header = next(cells for line, cells in rows if line == header_line)
    loaded = 0
    quarantined = 0
    seen = set()
    for line_number, cells in rows:
        if line_number <= header_line:
            continue
        raw = {
            header[index]: cells[index] if index < len(cells) else ""
            for index in range(len(header))
        }
        mapped = {}
        for source, value in raw.items():
            proposal = by_source.get(source)
            if proposal and proposal.canonical and not proposal.needs_confirmation:
                mapped[proposal.canonical] = value
        cleaned, reason = _clean_row(mapped)
        if reason:
            _quarantine(upload_id, line_number, reason, raw)
            quarantined += 1
            continue
        key = tuple(cleaned.get(column) for column in CANONICAL)
        if key in seen:
            _quarantine(upload_id, line_number, "duplicate", raw)
            quarantined += 1
            continue
        seen.add(key)
        _insert_sale(upload_id, workspace_id, cleaned)
        loaded += 1
    return loaded, quarantined


def _clean_row(mapped: dict[str, str]) -> tuple[dict | None, str | None]:
    if "order_date" not in mapped or parse_date(mapped.get("order_date", "")) is None:
        return None, "invalid date"
    cleaned = {"order_date": parse_date(mapped["order_date"]).isoformat()}
    for column in TEXT_COLUMNS:
        if column not in mapped:
            continue
        value = mapped[column].strip()
        if value:
            cleaned[column] = make_inert(value)
    if not cleaned.get("customer_id") and not cleaned.get("product_id"):
        return None, "missing identifier"
    for column in NUMBER_COLUMNS:
        if column not in mapped or not str(mapped[column]).strip():
            continue
        number = parse_number(mapped[column])
        if number is None:
            return None, f"invalid number in {column}"
        if column == "quantity":
            if number != number.to_integral_value():
                return None, "quantity is not a whole number"
            if number < 0:
                return None, "negative quantity"
            cleaned[column] = str(int(number))
            continue
        if column == "revenue" and number < 0:
            return None, "negative revenue"
        if column == "discount_pct" and (number < 0 or number > 100):
            return None, "impossible discount"
        if column == "unit_price" and number < 0:
            return None, "negative unit price"
        cleaned[column] = format(number, "f")
    if "revenue" not in cleaned and "quantity" not in cleaned:
        return None, "missing measure"
    return cleaned, None


def _quarantine(upload_id: int, line_number: int, reason: str, raw: dict) -> None:
    payload = json.dumps(raw, ensure_ascii=True)
    execute(
        "INSERT INTO quarantine (upload_id, row_number, reason, raw_json) "
        f"VALUES ({upload_id}, {int(line_number)}, {sql_literal(reason)}, "
        f"{sql_literal(payload)}::jsonb)"
    )


def _insert_sale(upload_id: int, workspace_id: int, cleaned: dict) -> None:
    columns = ["workspace_id", "upload_id", *cleaned.keys()]
    values = [str(int(workspace_id)), str(int(upload_id))]
    values.extend(sql_literal(cleaned[column]) for column in cleaned)
    execute(
        f"INSERT INTO sales_clean ({', '.join(columns)}) "
        f"VALUES ({', '.join(values)})"
    )
