"""Turn one spreadsheet into sales_clean rows, or reject it with a reason."""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from ingest.capabilities import compute_capabilities
from ingest.clean import make_inert, parse_date, parse_number
from ingest.mapping import (
    CANONICAL,
    Proposal,
    domain_gap,
    normalize,
    normalize_to_snake,
    propose_columns,
)
from ingest.safety import RejectedFile, inspect, stored_name
from ingest.store import execute, sql_literal
from ingest.tables import TableRejected, find_header, read_rows

ROOT = Path(__file__).resolve().parents[2]
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
    attributes_schema: list[dict] = field(default_factory=list)
    capabilities: dict = field(default_factory=dict)
    preview: list[dict] = field(default_factory=list)


def _emit(progress, stage: str, status: str, **extra) -> None:
    if progress is not None:
        progress({"event": "step", "stage": stage, "status": status, **extra})


def _mapping_payload(proposal: Proposal) -> dict:
    role = proposal.canonical if proposal.canonical else "attribute"
    return {
        "source": proposal.source,
        "canonical": proposal.canonical,
        "confidence": proposal.confidence,
        "method": proposal.method,
        "needs_confirmation": proposal.needs_confirmation,
        "confirmed_by_user": proposal.confirmed_by_user,
        "detected_role": role,
    }


def _load_confirmed_mappings(workspace_id: int) -> dict[str, str]:
    """Return {normalize(source_column): canonical_column} for confirmed mappings in this workspace."""
    try:
        rows = execute(
            "SELECT cm.source_column, cm.canonical_column "
            "FROM column_mapping cm "
            "JOIN uploads u ON u.id = cm.upload_id "
            f"WHERE u.workspace_id = {int(workspace_id)} "
            "AND cm.confirmed_by_user = true "
            "AND cm.canonical_column IS NOT NULL"
        )
        return {normalize(r["source_column"]): r["canonical_column"] for r in rows if r.get("canonical_column")}
    except Exception:
        return {}


def _collect_samples(rows: list[tuple[int, list[str]]], header_line: int, headers: list[str]) -> dict[str, list[str]]:
    """Collect up to 5 non-empty sample strings per header column."""
    samples: dict[str, list[str]] = {h: [] for h in headers}
    for line_number, cells in rows:
        if line_number <= header_line:
            continue
        for idx, h in enumerate(headers):
            if idx < len(cells):
                val = cells[idx].strip()
                if val and val not in samples[h] and len(samples[h]) < 5:
                    samples[h].append(val)
        if all(len(s) >= 5 for s in samples.values()):
            break
    return samples


def ingest(
    path: Path,
    workspace_id: int,
    confirm=None,
    *,
    upload_id: int | None = None,
    progress=None,
) -> IngestResult:
    result = _ingest(path, workspace_id, confirm, upload_id, progress)
    if progress is not None:
        progress(
            {
                "event": "done",
                "status": result.status,
                "reason": result.reason,
                "upload_id": result.upload_id,
                "stored_name": result.stored_name,
                "header_line": result.header_line,
                "loaded_rows": result.loaded_rows,
                "quarantined_rows": result.quarantined_rows,
                "mappings": [_mapping_payload(item) for item in result.mappings],
                "capabilities": result.capabilities,
                "preview": result.preview,
            }
        )
    return result


def _ingest(path, workspace_id: int, confirm, existing_id, progress) -> IngestResult:
    path = Path(path)
    try:
        data, extension = inspect(path)
    except RejectedFile as exc:
        _emit(progress, "safety", "error", reason=exc.reason)
        saved_id, name = _record_upload(
            path,
            workspace_id,
            "rejected",
            path.read_bytes() if path.is_file() else b"",
            existing_id,
        )
        return IngestResult("rejected", exc.reason, saved_id, name)
    _emit(progress, "safety", "done")

    try:
        rows = read_rows(path, extension)
    except TableRejected as exc:
        _emit(progress, "structure", "error", reason=exc.reason)
        saved_id, name = _record_upload(path, workspace_id, "rejected", data, existing_id)
        return IngestResult("rejected", exc.reason, saved_id, name)
    _emit(progress, "structure", "done")

    header_line, headers = find_header(rows)
    if header_line is None:
        _emit(progress, "profiling", "error", reason="could not find a header row")
        saved_id, name = _record_upload(path, workspace_id, "rejected", data, existing_id)
        return IngestResult("rejected", "could not find a header row", saved_id, name)
    _emit(progress, "profiling", "done", columns=len(headers))

    samples = _collect_samples(rows, header_line, headers)

    # Check remembered workspace confirmed mappings
    remembered = _load_confirmed_mappings(workspace_id)
    proposals = propose_columns(headers, samples=samples)
    if remembered:
        for p in proposals:
            norm = normalize(p.source)
            if norm in remembered:
                p.canonical = remembered[norm]
                p.confidence = 100.0
                p.method = "memory"
                p.needs_confirmation = False
                p.confirmed_by_user = True

    pending = [item for item in proposals if item.needs_confirmation]
    if pending and confirm is None:
        if domain_gap(_accepted_columns(proposals, include_pending=True)):
            reason = domain_gap(_accepted_columns(proposals, include_pending=True))
            _emit(progress, "mapping", "error", reason=reason)
            saved_id, name = _record_upload(path, workspace_id, "rejected", data, existing_id)
            _save_mappings(saved_id, proposals)
            return IngestResult("rejected", reason, saved_id, name, header_line, mappings=proposals)
        _emit(progress, "mapping", "needs_confirmation", pending=len(pending))
        saved_id, name = _record_upload(path, workspace_id, "needs_confirmation", data, existing_id)
        _save_mappings(saved_id, proposals)
        return IngestResult(
            "needs_confirmation",
            "confirm the low-confidence columns before loading rows",
            saved_id,
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
        _emit(progress, "mapping", "error", reason=gap)
        saved_id, name = _record_upload(path, workspace_id, "rejected", data, existing_id)
        _save_mappings(saved_id, proposals)
        return IngestResult("rejected", gap, saved_id, name, header_line, mappings=proposals)

    _emit(progress, "mapping", "done", pending=len(pending))
    saved_id, name = _record_upload(path, workspace_id, "accepted", data, existing_id)
    _save_mappings(saved_id, proposals)
    _emit(progress, "load", "running")
    loaded, quarantined, attr_schema, caps, preview = _load_rows(
        saved_id, workspace_id, rows, header_line, proposals
    )
    return IngestResult(
        "accepted",
        None,
        saved_id,
        name,
        header_line,
        loaded,
        quarantined,
        proposals,
        attributes_schema=attr_schema,
        capabilities=caps,
        preview=preview,
    )


def reserve_upload(original_name: str, workspace_id: int, data: bytes) -> tuple[int, Path]:
    suffix = Path(original_name).suffix.lower()
    extension = suffix if suffix in {".csv", ".xlsx"} else ".bin"
    digest = hashlib.sha256(data).hexdigest()
    name = stored_name(digest, extension)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = UPLOAD_DIR / name
    path.write_bytes(data)
    rows = execute(
        "INSERT INTO uploads "
        "(workspace_id, original_name, stored_name, sha256, size, status) "
        f"VALUES ({int(workspace_id)}, {sql_literal(Path(original_name).name)}, "
        f"{sql_literal(name)}, {sql_literal(digest)}, {len(data)}, 'received') "
        "RETURNING id"
    )
    return int(rows[0]["id"]), path


def confirm_mappings(upload_id: int, decisions: dict[str, str]) -> IngestResult:
    found = execute(
        "SELECT workspace_id, stored_name, status FROM uploads "
        f"WHERE id = {int(upload_id)}"
    )
    if not found:
        return IngestResult("rejected", "upload not found", upload_id)
    current = found[0]
    if current["status"] == "accepted":
        return IngestResult("rejected", "upload was already accepted", upload_id)
    path = UPLOAD_DIR / current["stored_name"]
    saved_mappings = execute(
        "SELECT source_column, canonical_column, confidence, method, confirmed_by_user "
        f"FROM column_mapping WHERE upload_id = {int(upload_id)}"
    )
    proposals = [
        Proposal(
            row["source_column"],
            row["canonical_column"] or None,
            float(row["confidence"] or 0),
            row["method"],
            needs_confirmation=False,
            confirmed_by_user=row["confirmed_by_user"] == "true",
        )
        for row in saved_mappings
    ]
    for proposal in proposals:
        if proposal.source in decisions:
            proposal.canonical = decisions[proposal.source]
            proposal.confirmed_by_user = True
            execute(
                f"UPDATE column_mapping SET canonical_column = {sql_literal(proposal.canonical)}, "
                "confirmed_by_user = true "
                f"WHERE upload_id = {int(upload_id)} AND source_column = {sql_literal(proposal.source)}"
            )
    columns = _accepted_columns(proposals, include_pending=False)
    gap = domain_gap(columns)
    if gap:
        return IngestResult("rejected", gap, upload_id, current["stored_name"], mappings=proposals)

    data = path.read_bytes()
    rows = read_rows(path, path.suffix.lower())
    header_line, _ = find_header(rows)
    execute(f"UPDATE uploads SET status = 'accepted' WHERE id = {int(upload_id)}")
    loaded, quarantined, attr_schema, caps, preview = _load_rows(
        int(upload_id), int(current["workspace_id"]), rows, header_line, proposals
    )
    return IngestResult(
        "accepted",
        None,
        int(upload_id),
        current["stored_name"],
        header_line,
        loaded,
        quarantined,
        proposals,
        attributes_schema=attr_schema,
        capabilities=caps,
        preview=preview,
    )


def _accepted_columns(proposals: list[Proposal], *, include_pending: bool) -> set[str]:
    accepted = set()
    for proposal in proposals:
        if not proposal.canonical:
            continue
        if proposal.needs_confirmation and not include_pending:
            continue
        accepted.add(proposal.canonical)
    return accepted


def _record_upload(path: Path, workspace_id: int, status: str, data: bytes, existing_id) -> tuple[int, str]:
    digest = hashlib.sha256(data).hexdigest()
    extension = path.suffix.lower()
    name = stored_name(digest, extension)
    if data:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        (UPLOAD_DIR / name).write_bytes(data)
    if existing_id is not None:
        execute(
            "UPDATE uploads SET "
            f"stored_name = {sql_literal(name)}, sha256 = {sql_literal(digest)}, "
            f"size = {len(data)}, status = {sql_literal(status)} "
            f"WHERE id = {int(existing_id)}"
        )
        return int(existing_id), name
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


def _infer_type(values: list[str]) -> str:
    """Infer numeric, date, or text from a list of non-empty sample strings."""
    if not values:
        return "text"
    is_num = True
    for v in values:
        try:
            Decimal(v.replace(",", "").replace("$", ""))
        except Exception:
            is_num = False
            break
    if is_num:
        return "numeric"
    is_dt = True
    for v in values:
        if parse_date(v) is None:
            is_dt = False
            break
    if is_dt:
        return "date"
    return "text"


def _save_attribute_schema(upload_id: int, all_attrs_rows: list[dict], total_rows: int) -> list[dict]:
    """Aggregate unmapped attributes, infer types, calculate null rates, and store in DB."""
    if total_rows == 0:
        return []
    all_keys = set()
    for r in all_attrs_rows:
        all_keys.update(r.keys())
    schema_records = []
    for key in sorted(all_keys):
        non_empty = [r[key] for r in all_attrs_rows if key in r and str(r[key]).strip()]
        null_count = total_rows - len(non_empty)
        null_rate = round(null_count / total_rows, 4)
        inferred = _infer_type(non_empty)
        # up to 5 unique sample values
        samples = list(dict.fromkeys(non_empty))[:5]
        samples_json = json.dumps(samples)
        execute(
            "INSERT INTO upload_attribute_schema "
            "(upload_id, key, inferred_type, null_rate, sample_values) "
            f"VALUES ({upload_id}, {sql_literal(key)}, {sql_literal(inferred)}, {null_rate}, {sql_literal(samples_json)}::jsonb) "
            "ON CONFLICT (upload_id, key) DO UPDATE SET "
            f"inferred_type = {sql_literal(inferred)}, null_rate = {null_rate}, sample_values = {sql_literal(samples_json)}::jsonb"
        )
        schema_records.append({
            "key": key,
            "inferred_type": inferred,
            "null_rate": null_rate,
            "sample_values": samples,
        })
    return schema_records


def _esc_tsv(val) -> str:
    if val is None or val == "":
        return r"\N"
    s = str(val)
    return s.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")

BATCH_COLUMNS = (
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
    "attributes",
)


def _insert_sales_batch(upload_id: int, workspace_id: int, batch: list[tuple[dict, dict]]) -> None:
    if not batch:
        return
    col_str = ", ".join(BATCH_COLUMNS)
    val_clauses = []
    for cleaned, attrs in batch:
        vals = [
            str(int(workspace_id)),
            str(int(upload_id)),
            sql_literal(cleaned.get("order_date")),
            sql_literal(cleaned.get("customer_id")),
            sql_literal(cleaned.get("product_id")),
            sql_literal(cleaned.get("quantity")),
            sql_literal(cleaned.get("revenue")),
            sql_literal(cleaned.get("unit_price")),
            sql_literal(cleaned.get("discount_pct")),
            sql_literal(cleaned.get("cost")),
            sql_literal(cleaned.get("profit")),
            sql_literal(cleaned.get("segment")),
            sql_literal(cleaned.get("region")),
            sql_literal(cleaned.get("category")),
            sql_literal(cleaned.get("sub_category")),
            sql_literal(cleaned.get("channel")),
            f"{sql_literal(json.dumps(attrs))}::jsonb",
        ]
        val_clauses.append(f"({', '.join(vals)})")
    execute(f"INSERT INTO sales_clean ({col_str}) VALUES {', '.join(val_clauses)}")


def _quarantine_batch(upload_id: int, batch: list[tuple[int, str, dict]]) -> None:
    if not batch:
        return
    val_clauses = []
    for line_number, reason, raw in batch:
        payload = json.dumps(raw, ensure_ascii=True)
        val_clauses.append(
            f"({upload_id}, {int(line_number)}, {sql_literal(reason)}, {sql_literal(payload)}::jsonb)"
        )
    execute(f"INSERT INTO quarantine (upload_id, row_number, reason, raw_json) VALUES {', '.join(val_clauses)}")


def _load_rows(upload_id, workspace_id, rows, header_line, proposals) -> tuple[int, int, list[dict], dict, list[dict]]:
    by_source = {proposal.source: proposal for proposal in proposals}
    header = next(cells for line, cells in rows if line == header_line)
    loaded = 0
    quarantined = 0
    seen = set()
    all_attrs_rows: list[dict] = []
    all_cleaned_rows: list[dict] = []
    preview_rows: list[dict] = []

    sales_buf = io.StringIO()
    quar_buf = io.StringIO()

    for line_number, cells in rows:
        if line_number <= header_line:
            continue
        raw = {
            header[index]: cells[index] if index < len(cells) else ""
            for index in range(len(header))
        }
        mapped = {}
        attrs = {}
        for source, value in raw.items():
            proposal = by_source.get(source)
            if proposal and proposal.canonical and not proposal.needs_confirmation:
                mapped[proposal.canonical] = value
            else:
                val = value.strip() if isinstance(value, str) else str(value or "")
                if val:
                    attrs[normalize_to_snake(source)] = val

        cleaned, reason = _clean_row(mapped)
        if reason:
            quar_buf.write(f"{upload_id}\t{line_number}\t{_esc_tsv(reason)}\t{_esc_tsv(json.dumps(raw))}\n")
            quarantined += 1
            continue
        key = tuple(cleaned.get(column) for column in CANONICAL)
        if key in seen:
            quar_buf.write(f"{upload_id}\t{line_number}\tduplicate\t{_esc_tsv(json.dumps(raw))}\n")
            quarantined += 1
            continue
        seen.add(key)

        cols = [
            str(workspace_id),
            str(upload_id),
            _esc_tsv(cleaned.get("order_date")),
            _esc_tsv(cleaned.get("customer_id")),
            _esc_tsv(cleaned.get("product_id")),
            _esc_tsv(cleaned.get("quantity")),
            _esc_tsv(cleaned.get("revenue")),
            _esc_tsv(cleaned.get("unit_price")),
            _esc_tsv(cleaned.get("discount_pct")),
            _esc_tsv(cleaned.get("cost")),
            _esc_tsv(cleaned.get("profit")),
            _esc_tsv(cleaned.get("segment")),
            _esc_tsv(cleaned.get("region")),
            _esc_tsv(cleaned.get("category")),
            _esc_tsv(cleaned.get("sub_category")),
            _esc_tsv(cleaned.get("channel")),
            _esc_tsv(json.dumps(attrs, ensure_ascii=False)),
        ]
        sales_buf.write("\t".join(cols) + "\n")
        loaded += 1
        all_attrs_rows.append(attrs)
        all_cleaned_rows.append(cleaned)
        if len(preview_rows) < 10:
            preview_rows.append({**cleaned, **attrs})

    sales_buf.seek(0)
    quar_buf.seek(0)

    # Driver-level COPY into staging and atomic commit into sales_clean
    from ingest.store import get_writer_connection
    conn = get_writer_connection()
    with conn:
        with conn.cursor() as cur:
            if loaded > 0:
                cur.execute("""
                    CREATE TEMP TABLE staging_sales AS SELECT * FROM sales_clean WITH NO DATA;
                    ALTER TABLE staging_sales DROP COLUMN id;
                """)
                cur.copy_expert(r"""
                    COPY staging_sales (
                        workspace_id, upload_id, order_date, customer_id, product_id,
                        quantity, revenue, unit_price, discount_pct, cost, profit,
                        segment, region, category, sub_category, channel, attributes
                    ) FROM STDIN WITH (FORMAT text, NULL '\N')
                """, sales_buf)
                cur.execute("""
                    INSERT INTO sales_clean (
                        workspace_id, upload_id, order_date, customer_id, product_id,
                        quantity, revenue, unit_price, discount_pct, cost, profit,
                        segment, region, category, sub_category, channel, attributes
                    ) SELECT
                        workspace_id, upload_id, order_date, customer_id, product_id,
                        quantity, revenue, unit_price, discount_pct, cost, profit,
                        segment, region, category, sub_category, channel, attributes
                    FROM staging_sales;
                """)

            if quarantined > 0:
                cur.execute("""
                    CREATE TEMP TABLE staging_quarantine AS SELECT * FROM quarantine WITH NO DATA;
                    ALTER TABLE staging_quarantine DROP COLUMN id;
                """)
                cur.copy_expert(r"""
                    COPY staging_quarantine (
                        upload_id, row_number, reason, raw_json
                    ) FROM STDIN WITH (FORMAT text, NULL '\N')
                """, quar_buf)
                cur.execute("""
                    INSERT INTO quarantine (upload_id, row_number, reason, raw_json)
                    SELECT upload_id, row_number, reason, raw_json FROM staging_quarantine;
                """)

            caps = compute_capabilities(all_cleaned_rows)
            cur.execute(
                "UPDATE uploads SET status = 'loaded', capabilities = %s WHERE id = %s",
                (json.dumps(caps), upload_id)
            )

    # Save attribute schema
    attr_schema = _save_attribute_schema(upload_id, all_attrs_rows, loaded)

    return loaded, quarantined, attr_schema, caps, preview_rows


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


def _insert_sale(upload_id: int, workspace_id: int, cleaned: dict, attributes: dict | None = None) -> None:
    columns = ["workspace_id", "upload_id", *cleaned.keys()]
    values = [str(int(workspace_id)), str(int(upload_id))]
    values.extend(sql_literal(cleaned[column]) for column in cleaned)
    if attributes:
        columns.append("attributes")
        values.append(f"{sql_literal(json.dumps(attributes))}::jsonb")
    execute(
        f"INSERT INTO sales_clean ({', '.join(columns)}) "
        f"VALUES ({', '.join(values)})"
    )
