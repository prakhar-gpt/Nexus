"""Upload ingestion and status tracking services."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import uuid
from pathlib import Path
from fastapi import BackgroundTasks, HTTPException, Response

from api.services.workspace_service import get_mappings, get_workspace_meta
from api.services.chat_service import format_sse
from agent.nexus.tools import SqlRejected, run_sql
from ingest import confirm_mappings, execute, ingest, make_inert, reserve_upload
from ingest.store import sql_id, sql_literal

PROGRESS: dict[int, list[dict]] = {}

# ---------------------------------------------------------------------------
# Persistent Agent Event Ledger (Shared Across All Nexus Agents)
# ---------------------------------------------------------------------------

_AGENT_SEQS: dict[int, int] = {}


def record_upload_event(
    upload_id: int,
    stage: str,
    event_type: str,
    label: str,
    payload: dict | None = None,
) -> dict:
    """Record an agent event in the unified agent_events table."""
    from ingest.store import execute, sql_literal

    seq = _AGENT_SEQS.get(upload_id, 0) + 1
    _AGENT_SEQS[upload_id] = seq

    event_payload = dict(payload or {})
    event_payload.setdefault("upload_id", upload_id)
    event_payload.setdefault("seq", seq)
    event_payload.setdefault("stage", stage)
    event_payload.setdefault("event_type", event_type)
    event_payload.setdefault("label", label)

    try:
        execute(
            f"INSERT INTO agent_events (agent_kind, upload_id, seq, stage, event_type, label, payload) "
            f"VALUES ('nexus', {sql_id(upload_id)}, {int(seq)}, {sql_literal(stage)}, {sql_literal(event_type)}, "
            f"{sql_literal(label)}, {sql_literal(json.dumps(event_payload))}::jsonb)"
        )
    except Exception:
        # Fallback to in-memory if DB transiently unready
        pass

    PROGRESS.setdefault(upload_id, []).append(event_payload)
    return event_payload


def fetch_upload_events_from_db(upload_id: int | str, since_seq: int = 0) -> list[dict]:
    """Retrieve ordered persistent agent events since a given sequence number."""
    from ingest.store import execute
    try:
        rows = execute(
            f"SELECT seq, stage, event_type, label, payload, created_at FROM agent_events "
            f"WHERE upload_id = {sql_id(upload_id)} AND seq > {int(since_seq)} "
            f"ORDER BY seq ASC"
        )
        events = []
        for r in rows:
            p = r.get("payload")
            data = json.loads(p) if isinstance(p, str) else dict(p or {})
            data.setdefault("seq", int(r["seq"]))
            data.setdefault("stage", r["stage"])
            data.setdefault("event_type", r["event_type"])
            data.setdefault("label", r["label"])
            events.append(data)
        return events
    except Exception:
        return [
            item for item in PROGRESS.get(upload_id, [])
            if item.get("seq", 0) > since_seq
        ]


# ---------------------------------------------------------------------------
# Deterministic helpers for chat-native architect events
# ---------------------------------------------------------------------------

# Maps architect tool names to plain-English present-tense labels
_ARCHITECT_TOOL_LABEL: dict[str, str] = {
    "list_columns":        "Listed columns",
    "profile_column":      "Profiled column",
    "test_parse":          "Tested type",
    "detect_date_format":  "Checked date format",
    "check_uniqueness":    "Checked key uniqueness",
    "sample_rows":         "Sampled rows",
}


def _architect_step_event(tool: str, status: str, args: dict | None = None, summary: str | None = None) -> dict:
    """Build a normalized `step` event payload shaped like the Nexus chat steps."""
    evidence: str | None = None
    if tool == "check_file":
        label = "Checked the file"
    elif tool == "read_types":
        label = "Read column types and null rates"
    elif tool == "detect_date_format":
        label = "Testing date format" if status == "running" else "Checked date format"
        if args and "column_name" in args:
            evidence = f"on {args['column_name']}"
    elif tool == "profile_column":
        label = "Inspecting column" if status == "running" else "Profiled column"
        if args and "column_name" in args:
            evidence = str(args["column_name"])
    elif tool == "test_parse":
        label = "Testing type" if status == "running" else "Tested type"
        if args:
            col = args.get("column_name", "")
            t = args.get("parse_type", "")
            evidence = f"{col} as {t}"
    elif tool == "check_uniqueness":
        label = "Checking key uniqueness" if status == "running" else "Checked key uniqueness"
        if args and "column_names" in args:
            cols = args["column_names"]
            evidence = f"on {', '.join(cols[:3])}" if isinstance(cols, list) else f"on {cols}"
    elif tool == "sample_rows":
        label = "Sampling rows" if status == "running" else "Sampled rows"
    else:
        label = _ARCHITECT_TOOL_LABEL.get(tool, tool)

    # Pull rate or date format from summary string if present
    if summary:
        import re
        if "parse_success_rate" in summary:
            m = re.search(r"parse_success_rate['\"]?\s*:\s*([\d.]+)", summary)
            if m:
                rate = float(m.group(1))
                evidence = (evidence or "") + f" ({round(rate * 100)}% parsed)"
        elif "candidate_formats" in summary:
            m = re.search(r"format['\"]?\s*:\s*['\"]([^'\"]+)['\"]", summary)
            if m:
                evidence = (evidence or "") + f" ({m.group(1)})"

    return {
        "event": "step",
        "id": str(uuid.uuid4())[:8],
        "tool": tool,
        "status": status,
        "label": label,
        "evidence": evidence,
    }


def _generate_suggested_questions(proposal: dict) -> list[dict]:
    """
    Deterministically generate up to 3 suggested questions from column roles.
    Prioritizes high-signal retail metrics (revenue, sales, profit) and dimensions (category, segment).
    """
    columns = proposal.get("columns") or []
    raw_measures    = [c["column_name"] for c in columns if c.get("role") == "measure"   and not c.get("excluded")]
    raw_dimensions  = [c["column_name"] for c in columns if c.get("role") == "dimension" and not c.get("excluded")]
    raw_dates       = [c["column_name"] for c in columns if c.get("role") == "date"       and not c.get("excluded")]
    raw_identifiers = [c["column_name"] for c in columns if c.get("role") == "identifier" and not c.get("excluded")]

    # Filter out any identifier-like columns that may have crept into measures
    non_measure_keywords = ("postal", "zip", "code", "phone", "fax", "ssn", "ein", "id", "nbr", "num")
    raw_measures = [m for m in raw_measures if not any(k in m.lower() for k in non_measure_keywords)]

    PRIORITY_MEASURES = ("revenue", "sales", "profit", "amount", "spend", "cost", "total", "margin", "quantity", "units", "discount")
    PRIORITY_DIMENSIONS = ("category", "sub_category", "segment", "region", "channel", "department", "state", "brand", "country")
    PRIORITY_DATES = ("order_date", "transaction_date", "date", "created_at", "ship_date")
    PRIORITY_IDS = ("customer_name", "customer_id", "product_name", "product_id", "store_name", "store_id", "item")

    def sort_by_priority(items: list[str], priority_list: tuple[str, ...]) -> list[str]:
        def rank(name: str):
            lower = name.lower()
            for idx, pfx in enumerate(priority_list):
                if pfx in lower:
                    return (0, idx)
            return (1, name)
        return sorted(items, key=rank)

    measures = sort_by_priority(raw_measures, PRIORITY_MEASURES)
    dimensions = sort_by_priority(raw_dimensions, PRIORITY_DIMENSIONS)
    dates = sort_by_priority(raw_dates, PRIORITY_DATES)
    identifiers = sort_by_priority(raw_identifiers, PRIORITY_IDS)

    suggestions: list[dict] = []

    if measures and dimensions:
        m = measures[0].replace("_", " ")
        d = dimensions[0].replace("_", " ")
        suggestions.append({
            "question": f"What is total {m} by {d}?",
            "hint": "measure × dimension",
        })

    if measures and dates:
        m  = measures[0].replace("_", " ")
        dt = dates[0].replace("_", " ")
        suggestions.append({
            "question": f"Show {m} over time by {dt}",
            "hint": "measure over date",
        })

    if measures and identifiers:
        m = measures[0].replace("_", " ")
        i = identifiers[0].replace("_", " ")
        suggestions.append({
            "question": f"Top 10 {i} by {m}",
            "hint": "top N by identifier",
        })

    if not suggestions and measures:
        m = measures[0].replace("_", " ")
        suggestions.append({
            "question": f"What is the total and average {m}?",
            "hint": "summary statistics",
        })

    return suggestions[:3]


def _emit_handoff(upload_id: int, table_name: str, table_label: str,
                  grain: str, loaded: int, quarantined: int, proposal: dict) -> None:
    """Record a deterministic `handoff` event for the given upload."""
    questions = _generate_suggested_questions(proposal)
    record_upload_event(
        upload_id=upload_id,
        stage="handoff",
        event_type="done",
        label=f"Dataset '{table_label}' loaded and ready for questions",
        payload={
            "event": "handoff",
            "table_name": table_name,
            "table_label": table_label,
            "grain": grain,
            "row_count": loaded,
            "quarantined_count": quarantined,
            "suggested_questions": questions,
        },
    )


def handle_file_upload(
    workspace_id: int | str,
    filename: str,
    data: bytes,
    background: BackgroundTasks,
) -> dict:
    """Validate file, allocate upload ID, and enqueue ingestion job."""
    if get_workspace_meta(workspace_id) is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    if len(data) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="file exceeds the 50 MB size cap")

    upload_id, path = reserve_upload(filename or "upload.csv", workspace_id, data)
    
    # Emit stage 1: received immediately
    record_upload_event(
        upload_id=upload_id,
        stage="received",
        event_type="done",
        label=f"Received {filename or 'file'}",
        payload={"file_name": filename, "file_size": len(data)},
    )
    
    background.add_task(run_ingest_job, upload_id, path, workspace_id)
    return {"upload_id": upload_id}


def run_ingest_job(upload_id: int | str, path, workspace_id: int | str) -> None:
    """Background ingestion task emitting canonical stage events."""
    def progress_callback(payload: dict) -> None:
        # Normalize architect_tool events into the shared `step` event shape
        if payload.get("event") == "architect_tool":
            tool    = payload.get("tool", "")
            args    = payload.get("args") or {}
            summary = payload.get("summary", "")
            # Mark previous step for the same tool as done (if any)
            items = PROGRESS.setdefault(upload_id, [])
            for item in reversed(items):
                if item.get("event") == "step" and item.get("tool") == tool and item.get("status") == "running":
                    item["status"] = "done"
                    break
            evt = _architect_step_event(tool, "running", args, summary)
            record_upload_event(
                upload_id=upload_id,
                stage="profile",
                event_type="step",
                label=evt.get("label", tool),
                payload=evt,
            )
        elif payload.get("event") == "step":
            stage_name = payload.get("stage") or "safety"
            st = payload.get("status") or "running"
            lbl = payload.get("label") or f"{stage_name.capitalize()} check"
            record_upload_event(
                upload_id=upload_id,
                stage=stage_name,
                event_type=st,
                label=lbl,
                payload=payload,
            )
        else:
            evt_name = payload.get("event", "progress")
            record_upload_event(
                upload_id=upload_id,
                stage=payload.get("stage", "profile"),
                event_type=evt_name,
                label=payload.get("label", evt_name),
                payload=payload,
            )

    try:
        # Stage 2: safety
        record_upload_event(upload_id, "safety", "start", "Checking file safety and macros…")
        res = ingest(path, workspace_id, upload_id=upload_id, progress=progress_callback, allow_custom_schema=True)
        if res.status == "rejected":
            record_upload_event(
                upload_id,
                "safety",
                "error",
                res.reason or "File safety check failed",
                payload={"event": "error", "final": "rejected", "status": "rejected", "reason": res.reason or "The file was rejected."},
            )
        elif res.status == "needs_schema_review":
            # Mark any open architect steps as done before emitting proposal-ready
            for item in PROGRESS.get(upload_id, []):
                if item.get("event") == "step" and item.get("status") == "running":
                    item["status"] = "done"
            _init_schema_proposal(upload_id, path, workspace_id, progress_callback)
        elif res.status == "needs_confirmation":
            record_upload_event(
                upload_id,
                "review",
                "needs_confirmation",
                res.reason or "Low-confidence columns require confirmation",
                payload={"event": "done", "final": "needs_confirmation", "status": "needs_confirmation", "reason": res.reason},
            )
        else:
            record_upload_event(
                upload_id,
                "load",
                "done",
                f"Loaded {res.loaded_rows} rows",
                payload={"event": "done", "final": "loaded", "status": "loaded", "loaded_rows": res.loaded_rows},
            )
    except Exception as exc:
        record_upload_event(
            upload_id,
            "error",
            "error",
            str(exc) or "Ingest failed",
            payload={"event": "error", "final": "rejected", "status": "rejected", "reason": str(exc) or "Ingest failed"},
        )


async def stream_upload_events(upload_id: int, since_seq: int = 0):
    """Yield Server-Sent Events tracking the progress of an ingestion job with replay and keepalive."""
    last_seq = int(since_seq)
    stale_ticks = 0

    while stale_ticks < 300:
        # 1. Fetch newly recorded events from persistent database ledger
        events = fetch_upload_events_from_db(upload_id, since_seq=last_seq)
        if events:
            for item in events:
                seq = item.get("seq", last_seq + 1)
                last_seq = max(last_seq, seq)
                event_name = item.get("event", "step")
                # Format SSE with id: <seq>
                raw_data = json.dumps(item)
                yield f"id: {seq}\nevent: {event_name}\ndata: {raw_data}\n\n"
                
                # Check for termination events
                if event_name in {"done", "error"} or item.get("final") in {"loaded", "rejected", "needs_schema_review", "needs_confirmation"}:
                    # Let client receive done/error and then exit cleanly
                    if item.get("stage") != "propose" or event_name == "done":
                        if event_name in {"done", "error"}:
                            return

        await asyncio.sleep(0.5)
        stale_ticks += 1
        # Send keepalive ping every 5 seconds (10 ticks * 0.5s)
        if stale_ticks % 10 == 0:
            yield ": keepalive\n\n"

    yield format_sse("error", {"message": "ingest stream timed out"})


def update_column_mappings(upload_id: int, decisions: dict[str, str]) -> dict:
    """Save user column confirmations and finalize loading into sales_clean."""
    result = confirm_mappings(upload_id, decisions)
    return {
        "status": result.status,
        "reason": result.reason,
        "upload_id": result.upload_id,
        "loaded_rows": result.loaded_rows,
        "quarantined_rows": result.quarantined_rows,
        "mappings": [
            {
                "source": item.source,
                "canonical": item.canonical,
                "confidence": item.confidence,
                "method": item.method,
                "needs_confirmation": item.needs_confirmation,
                "confirmed_by_user": item.confirmed_by_user,
            }
            for item in result.mappings
        ],
    }


def get_upload_health_summary(upload_id: int | str, download: str | None = None):
    """Return upload health summary or stream quarantine CSV download."""
    found = execute(
        "SELECT id, workspace_id, original_name, status FROM uploads "
        f"WHERE id = {sql_id(upload_id)}"
    )
    if not found:
        raise HTTPException(status_code=404, detail="upload not found")

    if download == "quarantine":
        rows = execute(
            "SELECT row_number, reason, raw_json FROM quarantine "
            f"WHERE upload_id = {sql_id(upload_id)} ORDER BY row_number"
        )
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["row_number", "reason", "raw_json"])
        for row in rows:
            writer.writerow(
                [
                    row["row_number"],
                    make_inert(row["reason"]),
                    make_inert(row["raw_json"]),
                ]
            )
        return Response(
            buffer.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=quarantine.csv"},
        )

    upload = found[0]
    summary = []
    # Check custom dataset row counts first
    ds = execute(f"SELECT table_name, row_count FROM datasets WHERE upload_id = {sql_id(upload_id)}")
    if ds:
        summary = [{"rows": str(ds[0].get("row_count", 0)), "first_order": "", "last_order": "", "revenue": ""}]
    else:
        try:
            summary = run_sql(
                "SELECT count(*) AS rows, min(order_date)::text AS first_order, "
                "max(order_date)::text AS last_order, "
                "coalesce(round(sum(revenue), 2)::text, '') AS revenue "
                f"FROM sales_clean WHERE upload_id = {sql_id(upload_id)}",
                upload["workspace_id"],
            )
        except SqlRejected:
            summary = []

    return {
        "upload_id": upload_id,
        "original_name": upload["original_name"],
        "status": upload["status"],
        "summary": summary[0] if summary else {},
        "mappings": get_mappings(upload_id),
    }


def get_upload_mapping_detail(upload_id: int | str) -> dict:
    """Retrieve column mapping proposals, capabilities, and preview for an upload."""
    found = execute(
        "SELECT workspace_id, stored_name, status, capabilities FROM uploads "
        f"WHERE id = {sql_id(upload_id)}"
    )
    if not found:
        raise HTTPException(status_code=404, detail="upload not found")
    upload = found[0]
    raw_caps = upload.get("capabilities") or "{}"
    try:
        caps = json.loads(raw_caps) if isinstance(raw_caps, str) else raw_caps
    except Exception:
        caps = {}
    mappings = get_mappings(upload_id)

    preview = []
    try:
        rows = run_sql(
            f"SELECT * FROM sales_clean WHERE upload_id = {sql_id(upload_id)} LIMIT 10",
            upload["workspace_id"],
        )
        for r in rows:
            attrs = {}
            if "attributes" in r and r["attributes"]:
                try:
                    attrs = json.loads(r["attributes"]) if isinstance(r["attributes"], str) else r["attributes"]
                except Exception:
                    pass
            clean_row = {k: v for k, v in r.items() if k not in ("attributes", "workspace_id", "upload_id")}
            preview.append({**clean_row, **attrs})
    except Exception:
        preview = []

    return {
        "mappings": mappings,
        "capabilities": caps or {},
        "preview": preview,
    }




# ---------------------------------------------------------------------------
# Schema Architect Endpoints & Business Logic
# ---------------------------------------------------------------------------

def _get_upload_df_and_rows(upload_id: int | str) -> tuple[dict, list[tuple[int, list[str]]], int, list[str], Any]:
    """Load parsed tabular data and pandas dataframe for an upload."""
    found = execute(
        f"SELECT id, workspace_id, original_name, stored_name, status, schema_proposal, custom_table_name "
        f"FROM uploads WHERE id = {sql_id(upload_id)}"
    )
    if not found:
        raise HTTPException(status_code=404, detail="upload not found")
    upload = found[0]
    stored = upload["stored_name"]
    from ingest.pipeline import UPLOAD_DIR
    from ingest.reader import find_header, read_rows
    path = UPLOAD_DIR / stored
    if not path.is_file():
        raise HTTPException(status_code=404, detail="upload file not found on disk")

    extension = path.suffix.lower()
    rows = read_rows(path, extension)
    header_line, headers = find_header(rows)
    if header_line is None:
        raise HTTPException(status_code=400, detail="header row not found in file")

    # Build pandas dataframe
    data_rows = []
    for line_num, cells in rows:
        if line_num <= header_line:
            continue
        row_dict = {
            headers[i]: cells[i].strip() if i < len(cells) else ""
            for i in range(len(headers))
        }
        data_rows.append(row_dict)

    import pandas as pd
    df = pd.DataFrame(data_rows)
    return upload, rows, header_line, headers, df


def _init_schema_proposal(upload_id: int | str, path, workspace_id: int | str, progress_callback=None) -> dict:
    """Generate or retrieve cached schema proposal and store on upload record."""
    from ingest.custom_table import compute_headers_hash, get_cached_proposal
    from ingest.reader import find_header, read_rows
    from agent.architect import run_schema_architect

    extension = path.suffix.lower()
    raw_rows = read_rows(path, extension)
    header_line, headers = find_header(raw_rows)
    header_hash = compute_headers_hash(headers)
    num_rows = max(0, len(raw_rows) - header_line - 1)

    record_upload_event(
        upload_id,
        "parse",
        "done",
        f"Parsed {len(headers)} columns",
        payload={
            "event": "step",
            "id": f"chk_{upload_id}",
            "tool": "check_file",
            "status": "done",
            "label": "Checked the file",
            "evidence": f"({len(headers)} columns, {num_rows:,} rows)",
        },
    )
    record_upload_event(
        upload_id,
        "profile",
        "done",
        "Read column types and null rates",
        payload={
            "event": "step",
            "id": f"types_{upload_id}",
            "tool": "read_types",
            "status": "done",
            "label": "Read column types and null rates",
        },
    )

    cached = get_cached_proposal(workspace_id, header_hash)
    if cached:
        cached["from_cache"] = True
        proposal_dict = cached
        record_upload_event(
            upload_id,
            "propose",
            "done",
            "Matches a previous schema",
            payload={
                "event": "step",
                "id": f"cached_{upload_id}",
                "tool": "cached_schema",
                "status": "done",
                "label": "Matched previous schema",
            },
        )
        record_upload_event(
            upload_id,
            "propose",
            "done",
            "Schema proposal ready (cached)",
            payload={
                "event": "architect_proposed",
                "proposal": proposal_dict,
                "matches_previous": True,
            },
        )
    else:
        # Build DataFrame and run Schema Architect agent
        record_upload_event(
            upload_id,
            "propose",
            "start",
            "Generating schema proposal…",
            payload={
                "event": "step",
                "id": f"propose_{upload_id}",
                "tool": "propose_schema",
                "status": "running",
                "label": "Analyzing schema proposal…",
            },
        )
        data_rows = []
        for line_num, cells in raw_rows:
            if line_num <= header_line:
                continue
            row_dict = {
                headers[i]: cells[i].strip() if i < len(cells) else ""
                for i in range(len(headers))
            }
            data_rows.append(row_dict)

        import pandas as pd
        df = pd.DataFrame(data_rows)

        upload_rows = execute(f"SELECT original_name FROM uploads WHERE id = {sql_id(upload_id)}")
        orig_name = upload_rows[0]["original_name"] if upload_rows and upload_rows[0].get("original_name") else path.name
        raw_stem = Path(orig_name).stem if orig_name else path.stem
        label = raw_stem.replace("_", " ").replace("-", " ").title()
        proposal_obj, tool_calls, lat, model_id = run_schema_architect(
            df,
            table_label=label,
            progress_callback=progress_callback,
        )
        proposal_dict = proposal_obj.model_dump()

    execute(
        f"UPDATE uploads SET schema_proposal = {sql_literal(json.dumps(proposal_dict))}::jsonb, "
        f"status = 'needs_schema_review' WHERE id = {sql_id(upload_id)}"
    )
    record_upload_event(
        upload_id,
        "review",
        "start",
        "Awaiting schema review",
        payload={
            "event": "done",
            "final": "needs_schema_review",
            "status": "needs_schema_review",
            "proposal": proposal_dict,
        },
    )
    return proposal_dict


def get_upload_schema(upload_id: int | str) -> dict:
    """GET /uploads/{id}/schema -> proposal + validation + 10-row preview."""
    upload, raw_rows, header_line, headers, df = _get_upload_df_and_rows(upload_id)
    raw_proposal = upload.get("schema_proposal")
    if not raw_proposal:
        # Generate on the fly if missing
        from ingest.pipeline import UPLOAD_DIR
        path = UPLOAD_DIR / upload["stored_name"]
        proposal = _init_schema_proposal(upload_id, path, upload["workspace_id"])
    else:
        proposal = json.loads(raw_proposal) if isinstance(raw_proposal, str) else raw_proposal

    from ingest.schema_validation import validate_schema_proposal
    col_data = {str(c): [str(x) for x in df[c].tolist()] for c in df.columns}
    val_res = validate_schema_proposal(proposal, headers, column_data=col_data)

    # 10-row preview reflecting columns
    preview = []
    for _, row in df.head(10).iterrows():
        preview.append({str(k): str(v) for k, v in row.items()})

    return {
        "upload_id": upload_id,
        "workspace_id": upload["workspace_id"],
        "status": upload["status"],
        "table_name": upload.get("custom_table_name") or f"ds_{str(upload_id).replace('-', '_')}",
        "proposal": proposal,
        "validation": val_res.model_dump(),
        "preview": preview,
    }


def initiate_upload_schema(upload_id: int | str) -> dict:
    """Trigger Schema Architect manually (e.g. from 'Or load as custom table instead')."""
    upload, raw_rows, header_line, headers, df = _get_upload_df_and_rows(upload_id)
    from ingest.pipeline import UPLOAD_DIR
    path = UPLOAD_DIR / upload["stored_name"]
    _init_schema_proposal(upload_id, path, upload["workspace_id"])
    return get_upload_schema(upload_id)


def update_upload_schema(upload_id: int | str, proposal_edits: dict) -> dict:
    """PUT /uploads/{id}/schema -> save user edits and revalidate."""
    upload, raw_rows, header_line, headers, df = _get_upload_df_and_rows(upload_id)

    from ingest.schema_validation import validate_schema_proposal
    col_data = {str(c): [str(x) for x in df[c].tolist()] for c in df.columns}
    val_res = validate_schema_proposal(proposal_edits, headers, column_data=col_data)

    execute(
        f"UPDATE uploads SET schema_proposal = {sql_literal(json.dumps(proposal_edits))}::jsonb "
        f"WHERE id = {sql_id(upload_id)}"
    )

    return {
        "upload_id": upload_id,
        "proposal": proposal_edits,
        "validation": val_res.model_dump(),
    }


def approve_upload_schema(
    upload_id: int,
    background: BackgroundTasks | None = None,
    thread_id: str | None = None,
) -> dict:
    """POST /uploads/{id}/schema/approve -> validate, build DDL, create table, load COPY rows."""
    upload, raw_rows, header_line, headers, df = _get_upload_df_and_rows(upload_id)
    raw_proposal = upload.get("schema_proposal")
    if not raw_proposal:
        raise HTTPException(status_code=400, detail="No schema proposal to approve.")

    proposal = json.loads(raw_proposal) if isinstance(raw_proposal, str) else raw_proposal

    from ingest.schema_validation import validate_schema_proposal
    col_data = {str(c): [str(x) for x in df[c].tolist()] for c in df.columns}
    val_res = validate_schema_proposal(proposal, headers, column_data=col_data)

    if not val_res.is_valid:
        raise HTTPException(
            status_code=400,
            detail={"message": "Schema approval blocked by validation errors.", "errors": [e.model_dump() for e in val_res.errors]},
        )

    # Execute custom table creation and row load
    from ingest.custom_table import compute_headers_hash, create_and_load_custom_table
    header_hash = compute_headers_hash(headers)

    def progress_callback(payload: dict) -> None:
        # Normalize load_progress events with percentage
        if payload.get("event") == "load_progress":
            loaded_so_far = payload.get("loaded", 0)
            total_rows = max(1, len(raw_rows) - header_line - 1)
            pct = min(99, round(loaded_so_far / total_rows * 100))
            record_upload_event(
                upload_id,
                "load",
                "progress",
                f"Loading rows ({pct}%)",
                payload={
                    "event": "load_progress",
                    "loaded": loaded_so_far,
                    "pct": pct,
                },
            )
        else:
            evt_name = payload.get("event", "progress")
            record_upload_event(
                upload_id,
                "load",
                evt_name,
                payload.get("label", evt_name),
                payload=payload,
            )

    record_upload_event(upload_id, "create", "start", "Creating custom table…", payload={"event": "schema_approved", "table_name": f"ds_{upload_id}"})
    record_upload_event(upload_id, "create", "done", "Custom table created", payload={"event": "table_created", "table_name": f"ds_{upload_id}"})
    record_upload_event(upload_id, "load", "start", "Loading dataset rows…")

    # Compute clean friendly dataset label from original filename or proposal
    import re
    orig = upload.get("original_name") or ""
    clean_orig = Path(orig).stem.replace("_", " ").replace("-", " ").title() if orig else ""
    table_lbl = (proposal.get("table_label") or "").strip()
    is_hash = bool(re.match(r"^[0-9a-fA-F]{12,}$", table_lbl)) or table_lbl.lower().startswith("ds_")
    if clean_orig and (not table_lbl or is_hash or table_lbl.lower() == "custom dataset"):
        friendly_label = clean_orig
    else:
        friendly_label = table_lbl or clean_orig or f"Dataset {upload_id}"
    if friendly_label.lower().endswith(('.csv', '.xlsx', '.xls', '.tsv')):
        friendly_label = friendly_label.rsplit('.', 1)[0]

    loaded, quarantined, table_name = create_and_load_custom_table(
        upload_id=upload_id,
        workspace_id=upload["workspace_id"],
        table_label=friendly_label,
        grain=proposal.get("grain", ""),
        grain_key_columns=proposal.get("grain_key_columns", []),
        columns=proposal.get("columns", []),
        raw_rows=raw_rows,
        header_line=header_line,
        header_hash=header_hash,
        proposal_json=proposal,
        progress_callback=progress_callback,
    )

    execute(f"UPDATE uploads SET status = 'loaded' WHERE id = {sql_id(upload_id)}")

    # Auto-check newly approved dataset in active thread if one exists
    new_ds_row = execute(f"SELECT id FROM datasets WHERE upload_id = {sql_id(upload_id)}")
    if new_ds_row:
        new_ds_id = str(new_ds_row[0]["id"])
        latest_thread = execute(
            f"SELECT id FROM threads WHERE workspace_id = {sql_id(upload['workspace_id'])} ORDER BY updated_at DESC LIMIT 1"
        )
        if latest_thread:
            t_id = latest_thread[0]["id"]
            execute(
                f"UPDATE threads SET selected_dataset_ids = array_append(selected_dataset_ids, {sql_literal(str(new_ds_id))}), updated_at = now() "
                f"WHERE workspace_id = {sql_id(upload['workspace_id'])} AND id = {sql_literal(t_id)} "
                f"AND NOT ({sql_literal(str(new_ds_id))} = ANY(selected_dataset_ids))"
            )

    questions = _generate_suggested_questions(proposal)

    # Resolve thread for this upload so the conversation history is preserved on reload
    clean_thread = (thread_id or "").strip()
    if not clean_thread:
        latest_t = execute(
            f"SELECT id FROM threads WHERE workspace_id = {sql_id(upload['workspace_id'])} ORDER BY updated_at DESC LIMIT 1"
        )
        clean_thread = latest_t[0]["id"] if latest_t else "default"

    from api.services.workspace_service import get_or_create_thread
    get_or_create_thread(upload["workspace_id"], clean_thread)

    clean_grain = re.sub(
        r"^[\s*#_-]*(?:grain|table grain|one row represents)[\s*#_:-]*",
        "",
        proposal.get("grain", "") or "",
        flags=re.I,
    ).strip()
    handoff_text = f"I've loaded {friendly_label} ({clean_grain}, {loaded:,} rows). Here's what you can ask:"
    orig_name = upload.get("original_name") or f"{friendly_label}.csv"
    question_text = f"Uploaded dataset: {orig_name}"
    checker_payload = {
        "thread_id": clean_thread,
        "kind": "upload",
        "verified": True,
        "table_name": table_name,
        "table_label": friendly_label,
        "grain": clean_grain,
        "row_count": loaded,
        "quarantined_count": quarantined,
        "suggested_questions": questions,
        "handoff_data": {
            "tableLabel": friendly_label,
            "tableName": table_name,
            "grain": clean_grain,
            "rowCount": loaded,
            "quarantinedCount": quarantined,
            "suggestedQuestions": questions,
        },
    }

    checker_payload["upload_id"] = str(upload_id)

    # Clean any stale upload run for this upload_id, then persist the human-readable turn
    execute(
        f"DELETE FROM runs WHERE workspace_id = {sql_id(upload['workspace_id'])} AND (checker_result->>'upload_id') = {sql_literal(str(upload_id))};\n"
        f"INSERT INTO runs (workspace_id, question, answer, checker_result, latency_ms) "
        f"VALUES ({sql_id(upload['workspace_id'])}, {sql_literal(question_text)}, {sql_literal(handoff_text)}, "
        f"{sql_literal(json.dumps(checker_payload))}::jsonb, 0);"
    )

    # Emit handoff BEFORE done so frontend receives it in stream order
    _emit_handoff(
        upload_id=upload_id,
        table_name=table_name,
        table_label=friendly_label,
        grain=proposal.get("grain", ""),
        loaded=loaded,
        quarantined=quarantined,
        proposal=proposal,
    )

    record_upload_event(
        upload_id,
        "load",
        "done",
        f"Loaded {loaded} rows into {table_name}",
        payload={
            "event": "done",
            "final": "loaded",
            "status": "loaded",
            "loaded_rows": loaded,
            "quarantined_rows": quarantined,
            "table_name": table_name,
            "table_label": friendly_label,
        },
    )

    return {
        "status": "loaded",
        "dataset_id": new_ds_id if new_ds_row else None,
        "table_name": table_name,
        "table_label": friendly_label,
        "grain": proposal.get("grain", ""),
        "loaded_rows": loaded,
        "quarantined_rows": quarantined,
        "suggested_questions": questions,
    }


def reject_upload_schema(upload_id: int | str) -> dict:
    """POST /uploads/{id}/schema/reject -> mark rejected, no table created."""
    execute(f"UPDATE uploads SET status = 'rejected' WHERE id = {sql_id(upload_id)}")
    record_upload_event(
        upload_id,
        "review",
        "error",
        "Rejected by user during schema review",
        payload={
            "event": "done",
            "final": "rejected",
            "status": "rejected",
            "reason": "Rejected by user during schema review.",
        },
    )
    return {"status": "rejected", "message": "Schema rejected. No table was created."}


def regenerate_upload_schema(upload_id: int | str, user_hint: str | None = None) -> dict:
    """POST /uploads/{id}/schema/regenerate -> re-run architect (capped at 3 runs)."""
    upload, raw_rows, header_line, headers, df = _get_upload_df_and_rows(upload_id)

    # Cap check
    runs_count_res = execute(f"SELECT count(*) AS cnt FROM runs WHERE upload_id = {sql_id(upload_id)}")
    runs_count = int(runs_count_res[0]["cnt"]) if runs_count_res else 0
    if runs_count >= 3:
        raise HTTPException(status_code=429, detail="Maximum 3 regeneration runs reached for this upload.")

    from agent.architect import run_schema_architect
    label = upload["original_name"].rsplit(".", 1)[0].replace("_", " ").title()

    def progress_callback(payload: dict) -> None:
        PROGRESS.setdefault(upload_id, []).append(payload)

    proposal_obj, tool_calls, lat, model_id = run_schema_architect(
        df,
        table_label=label,
        user_hint=user_hint,
        progress_callback=progress_callback,
    )
    proposal_dict = proposal_obj.model_dump()

    execute(
        f"UPDATE uploads SET schema_proposal = {sql_literal(json.dumps(proposal_dict))}::jsonb WHERE id = {sql_id(upload_id)};"
    )

    PROGRESS.setdefault(upload_id, []).append({
        "event": "architect_proposed",
        "proposal": proposal_dict,
        "regenerated": True,
    })

    return {
        "status": "regenerated",
        "run_count": runs_count + 1,
        "proposal": proposal_dict,
    }


def get_upload_status_for_rehydration(upload_id: int | str) -> dict:
    """GET /uploads/{id}/status — returns upload status, proposal, table metadata and suggested questions.
    Used by the frontend to restore the architect card and handoff message on page reload."""
    rows = execute(
        f"SELECT u.id, u.original_name, u.status, u.schema_proposal, u.custom_table_name, "
        f"u.workspace_id, u.size, "
        f"d.table_label, d.grain, d.row_count, "
        f"(SELECT count(*)::int FROM quarantine q WHERE q.upload_id = u.id) AS quarantine_count "
        f"FROM uploads u "
        f"LEFT JOIN datasets d ON d.upload_id = u.id "
        f"WHERE u.id = {sql_id(upload_id)}"
    )
    if not rows:
        raise HTTPException(status_code=404, detail="upload not found")
    row = rows[0]
    proposal = None
    if row.get("schema_proposal"):
        raw = row["schema_proposal"]
        proposal = json.loads(raw) if isinstance(raw, str) else raw

    suggested_questions: list[dict] = []
    if proposal and row.get("status") == "loaded":
        suggested_questions = _generate_suggested_questions(proposal)

    return {
        "upload_id": upload_id,
        "file_name": row.get("original_name", ""),
        "status": row.get("status", "uploading"),
        "table_name": row.get("custom_table_name"),
        "table_label": row.get("table_label"),
        "grain": row.get("grain"),
        "loaded_rows": int(row.get("row_count") or 0),
        "quarantined_rows": int(row.get("quarantine_count") or 0),
        "proposal": proposal,
        "suggested_questions": suggested_questions,
    }
