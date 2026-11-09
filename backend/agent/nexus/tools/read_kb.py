"""read_kb tool: safe markdown reference reader within the knowledge base directory."""

from __future__ import annotations

from pathlib import Path
from langchain_core.tools import tool

try:
    from config import settings
    _custom_kb = Path(settings.NEXUS_TOOL_KB_DIR)
    KB_ROOT = _custom_kb if _custom_kb.is_absolute() else Path(__file__).resolve().parents[2] / _custom_kb.name
    KB_MAX_CHARS = settings.NEXUS_TOOL_KB_MAX_CHARS
except Exception:
    KB_ROOT = Path(__file__).resolve().parents[2] / "kb"
    KB_MAX_CHARS = 6000


@tool
def read_kb(path: str) -> str:
    """Read one knowledge-base file by name, such as column_hints.md."""


def execute_kb(path: str) -> str:
    """Safely read a knowledge base markdown file within backend/kb/."""
    root = KB_ROOT.resolve()
    name = str(path or "").replace("\\", "/").strip().lstrip("/")
    if not name or ".." in name.split("/"):
        return "rejected: path is outside the knowledge base"
    candidate = (root / name).resolve()
    if candidate != root and root not in candidate.parents:
        return "rejected: path is outside the knowledge base"
    if not candidate.is_file():
        return "rejected: file not found"
    return candidate.read_text(encoding="utf-8")[:KB_MAX_CHARS]
