"""Tabular file safety inspection, workbook extraction (CSV/XLSX), and cell parsing."""

from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
from pathlib import Path
import zipfile

from openpyxl import load_workbook

from ingest.mapping import propose_columns

MAX_BYTES = 50 * 1024 * 1024
ALLOWED_EXTENSIONS = {".csv", ".xlsx"}
MAX_COLUMNS = 64
MAX_ROWS = 200_000
HEADER_SCAN = 20
_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y")
_FORMULA_PREFIXES = ("=", "+", "-", "@")


class RejectedFile(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class TableRejected(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def inspect(path: Path) -> tuple[bytes, str]:
    """Validate file existence, size, extension, and binary safety."""
    if not path.is_file():
        raise RejectedFile("file not found")
    size = path.stat().st_size
    if size == 0:
        raise RejectedFile("empty file")
    if size > MAX_BYTES:
        raise RejectedFile("file exceeds the 50 MB size cap")
    data = path.read_bytes()
    extension = path.suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise RejectedFile("only csv and xlsx files are accepted")
    if _is_zip(data) and _zip_has_macro(data):
        raise RejectedFile("macro-enabled workbooks are rejected")
    if extension == ".csv" and _is_zip(data):
        raise RejectedFile("file content does not match the csv extension")
    if extension == ".xlsx" and not _is_zip(data):
        raise RejectedFile("file content does not match the xlsx extension")
    if extension == ".csv" and b"\x00" in data[:1024]:
        raise RejectedFile("file content is not text")
    return data, extension


def stored_name(digest: str, extension: str) -> str:
    """Generate deterministic content-addressed filename."""
    return f"{digest[:16]}{extension}"


def _is_zip(data: bytes) -> bool:
    return data.startswith(b"PK")


def _zip_has_macro(data: bytes) -> bool:
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            names = {name.lower() for name in archive.namelist()}
    except zipfile.BadZipFile:
        return False
    return any(name.endswith("vbaproject.bin") for name in names)


def read_rows(path: Path, extension: str) -> list[tuple[int, list[str]]]:
    """Read CSV or XLSX into line-indexed string lists."""
    if extension == ".csv":
        return _read_csv(path)
    return _read_xlsx(path)


def _read_csv(path: Path) -> list[tuple[int, list[str]]]:
    text = path.read_text(encoding="utf-8-sig")
    if not text.strip():
        raise TableRejected("empty file")
    rows = []
    for line_number, cells in enumerate(csv.reader(StringIO(text)), start=1):
        if not any(str(cell).strip() for cell in cells):
            continue
        rows.append((line_number, [str(cell).strip() for cell in cells]))
        if len(rows) > MAX_ROWS:
            raise TableRejected("file exceeds the row cap")
    if not rows:
        raise TableRejected("empty file")
    width = max(len(cells) for _, cells in rows)
    if width > MAX_COLUMNS:
        raise TableRejected("file exceeds the column cap")
    if width < 2:
        raise TableRejected("single-column file")
    return rows


def _read_xlsx(path: Path) -> list[tuple[int, list[str]]]:
    workbook = load_workbook(path, read_only=True, data_only=False)
    try:
        scored = []
        for sheet in workbook.worksheets:
            rows = _sheet_rows(sheet)
            if not rows:
                continue
            scored.append((header_hits(rows), sheet.title, rows))
        if not scored:
            raise TableRejected("empty file")
        scored.sort(key=lambda item: item[0], reverse=True)
        if len(scored) > 1 and scored[0][0] == scored[1][0] and scored[0][0] >= 2:
            raise TableRejected("multiple sheets match; ask which sheet to use")
        rows = scored[0][2]
    finally:
        workbook.close()
    width = max(len(cells) for _, cells in rows)
    if width > MAX_COLUMNS:
        raise TableRejected("file exceeds the column cap")
    if width < 2:
        raise TableRejected("single-column file")
    return rows


def _sheet_rows(sheet) -> list[tuple[int, list[str]]]:
    rows = []
    for index, raw in enumerate(sheet.iter_rows(values_only=True), start=1):
        cells = ["" if cell is None else str(cell).strip() for cell in raw]
        if not any(cells):
            continue
        rows.append((index, cells))
        if len(rows) > MAX_ROWS:
            raise TableRejected("file exceeds the row cap")
    return rows


def header_hits(rows: list[tuple[int, list[str]]]) -> int:
    header_line, _ = find_header(rows)
    if header_line is None:
        return 0
    for line_number, cells in rows:
        if line_number == header_line:
            return sum(1 for cell in cells if _is_header_cell(cell))
    return 0


def find_header(rows: list[tuple[int, list[str]]]) -> tuple[int | None, list[str]]:
    """Locate the row index that best matches canonical column headers."""
    best_line = None
    best_cells: list[str] = []
    best_hits = 0
    for line_number, cells in rows[:HEADER_SCAN]:
        hits = sum(1 for cell in cells if _is_header_cell(cell))
        if hits > best_hits:
            best_hits = hits
            best_line = line_number
            best_cells = cells
    if best_hits >= 2 and best_line is not None:
        return best_line, best_cells
    for line_number, cells in rows:
        filled = [cell for cell in cells if cell]
        if len(filled) >= 2:
            return line_number, cells
    return None, []


def _is_header_cell(cell: str) -> bool:
    if not cell:
        return False
    proposals = propose_columns([cell])
    proposal = proposals[0]
    return proposal.canonical is not None and (
        not proposal.needs_confirmation or proposal.confidence >= 50
    )


def parse_date(value: str):
    """Parse dates in standard ISO and retail day/month/year formats."""
    text = (value or "").strip()
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_number(value: str) -> Decimal | None:
    """Parse commercial numbers: strips currency symbols, percentage signs, commas."""
    text = (value or "").strip()
    if not text:
        return None
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1].strip()
    for symbol in ("$", "€", "£", ","):
        text = text.replace(symbol, "")
    text = text.replace(" ", "")
    if text.endswith("%"):
        text = text[:-1]
    if not text:
        return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    return -number if negative else number


def make_inert(value: str) -> str:
    """Escape CSV formula injection triggers (=, +, -, @) with a leading quote."""
    if not value:
        return value
    if value.startswith("'"):
        return value
    if value[0] in _FORMULA_PREFIXES:
        return "'" + value
    return value

