"""Upload file ingestion, binary safety verification, and Schema Architect routing."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from db.models import Upload
from db.session import session_scope
from ingest.reader import RejectedFile, TableRejected, find_header, inspect, read_rows, stored_name
from utils import to_uuid

ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = ROOT / "datasets" / "uploads"


@dataclass
class IngestResult:
    status: str
    reason: str | None = None
    upload_id: str | None = None
    stored_name: str | None = None
    header_line: int | None = None
    loaded_rows: int = 0
    quarantined_rows: int = 0
    mappings: list[dict] = field(default_factory=list)
    attributes_schema: list[dict] = field(default_factory=list)
    capabilities: dict = field(default_factory=dict)
    preview: list[dict] = field(default_factory=list)


def _emit(progress, stage: str, status: str, **extra) -> None:
    if progress is not None:
        progress({"event": "step", "stage": stage, "status": status, **extra})


def _record_upload(
    path: Path,
    workspace_id: int | str,
    status: str,
    data: bytes,
    existing_id: str | None = None,
) -> tuple[str, str]:
    digest = hashlib.sha256(data).hexdigest()
    extension = path.suffix.lower()
    name = stored_name(digest, extension)
    if data:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        (UPLOAD_DIR / name).write_bytes(data)

    ws_uuid = to_uuid(workspace_id)
    with session_scope() as session:
        if existing_id is not None:
            up_uuid = to_uuid(existing_id)
            up = session.get(Upload, up_uuid)
            if up:
                up.stored_name = name
                up.sha256 = digest
                up.size = len(data)
                up.status = status
                return str(up.id), name

        up = Upload(
            workspace_id=ws_uuid,
            original_name=path.name,
            stored_name=name,
            sha256=digest,
            size=len(data),
            status=status,
        )
        session.add(up)
        session.flush()
        return str(up.id), name


def reserve_upload(original_name: str, workspace_id: int | str, data: bytes) -> tuple[str, Path]:
    """Store raw workbook file and allocate an upload tracking record."""
    suffix = Path(original_name).suffix.lower()
    extension = suffix if suffix in {".csv", ".xlsx"} else ".bin"
    digest = hashlib.sha256(data).hexdigest()
    name = stored_name(digest, extension)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = UPLOAD_DIR / name
    path.write_bytes(data)

    ws_uuid = to_uuid(workspace_id)
    with session_scope() as session:
        up = Upload(
            workspace_id=ws_uuid,
            original_name=Path(original_name).name,
            stored_name=name,
            sha256=digest,
            size=len(data),
            status="received",
        )
        session.add(up)
        session.flush()
        return str(up.id), path


def ingest(
    path: Path,
    workspace_id: int | str,
    confirm: Any = None,
    *,
    upload_id: str | None = None,
    progress: Any = None,
    allow_custom_schema: bool = True,
) -> IngestResult:
    """Validate tabular safety, locate header, and route workbook to Schema Architect."""
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
            upload_id,
        )
        return IngestResult("rejected", exc.reason, saved_id, name)
    _emit(progress, "safety", "done")

    try:
        rows = read_rows(path, extension)
    except TableRejected as exc:
        _emit(progress, "structure", "error", reason=exc.reason)
        saved_id, name = _record_upload(path, workspace_id, "rejected", data, upload_id)
        return IngestResult("rejected", exc.reason, saved_id, name)
    _emit(progress, "structure", "done")

    header_line, headers = find_header(rows)
    if header_line is None:
        _emit(progress, "profiling", "error", reason="could not find a header row")
        saved_id, name = _record_upload(path, workspace_id, "rejected", data, upload_id)
        return IngestResult("rejected", "could not find a header row", saved_id, name)
    _emit(progress, "profiling", "done", columns=len(headers))

    # All sheet uploads route dynamically to Schema Architect for profiling
    _emit(progress, "schema_architect", "running", detail="Schema Architect is analyzing column shapes…")
    saved_id, name = _record_upload(path, workspace_id, "needs_schema_review", data, upload_id)
    result = IngestResult("needs_schema_review", None, saved_id, name, header_line)

    if progress is not None:
        progress(
            {
                "event": "done",
                "status": result.status,
                "reason": result.reason,
                "upload_id": result.upload_id,
                "stored_name": result.stored_name,
                "header_line": result.header_line,
                "loaded_rows": 0,
                "quarantined_rows": 0,
                "mappings": [],
                "capabilities": {},
                "preview": [],
            }
        )
    return result
