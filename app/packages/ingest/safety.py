"""File safety checks. Cells are never evaluated."""

from __future__ import annotations

import zipfile
from pathlib import Path

MAX_BYTES = 20 * 1024 * 1024
ALLOWED_EXTENSIONS = {".csv", ".xlsx"}


class RejectedFile(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def inspect(path: Path) -> tuple[bytes, str]:
    if not path.is_file():
        raise RejectedFile("file not found")
    size = path.stat().st_size
    if size == 0:
        raise RejectedFile("empty file")
    if size > MAX_BYTES:
        raise RejectedFile("file exceeds the 20 MB size cap")
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
    return f"{digest[:16]}{extension}"


def _is_zip(data: bytes) -> bool:
    return data.startswith(b"PK")


def _zip_has_macro(data: bytes) -> bool:
    from io import BytesIO

    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            names = {name.lower() for name in archive.namelist()}
    except zipfile.BadZipFile:
        return False
    return any(name.endswith("vbaproject.bin") for name in names)
