"""Core utility functions for Nexus backend: identifiers, parsing, and formatting."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any
from fastapi import HTTPException


def to_uuid(val: Any) -> uuid.UUID:
    """Coerce string, int, or UUID into a valid uuid.UUID."""
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except (ValueError, AttributeError):
        try:
            return uuid.UUID(int=int(val))
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail=f"Invalid UUID: {val}")


def parse_dataset_ids(raw: Any) -> list[str]:
    """Parse Postgres text[], uuid[], list, or string into a clean list of string IDs."""
    if not raw:
        return []
    if isinstance(raw, str):
        clean_s = raw.strip("{}").strip()
        if not clean_s:
            return []
        return [x.strip().strip('"') for x in clean_s.split(",") if x.strip()]
    if isinstance(raw, (list, tuple, set)):
        return [str(x) for x in raw if str(x).strip()]
    return []


def clean_grain(raw: str | None) -> str:
    """Normalize human-entered or LLM-generated table grain description."""
    if not raw:
        return ""
    cleaned = re.sub(
        r"^[\s*#_-]*(?:grain|table grain|one row represents)[\s*#_:-]*",
        "",
        str(raw).strip(),
        flags=re.IGNORECASE,
    ).strip()
    return cleaned


def sanitize_identifier(name: str, max_length: int = 63) -> str:
    """Convert an arbitrary label or header into a safe PostgreSQL snake_case identifier."""
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", str(name).strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"col_{cleaned}"
    return cleaned[:max_length]


def make_inert(value: Any) -> str:
    """Prefix leading spreadsheet formula characters to neutralize CSV formula injection."""
    s = str(value) if value is not None else ""
    if s.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{s}"
    return s


def esc_tsv(val: Any) -> str:
    """Escape a value for PostgreSQL text-format streaming COPY (tab-delimited, \\N for null)."""
    if val is None or val == "":
        return r"\N"
    s = str(val)
    return s.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")


def format_sse(event: str, payload: dict[str, Any]) -> str:
    """Format a Server-Sent Event message with json data."""
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"
