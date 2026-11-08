"""Text extraction and formatting utilities for model tokens and messages."""

from __future__ import annotations


def extract_visible_text(message) -> str:
    """Extract user-facing text from message, filtering out internal reasoning blocks."""
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
                continue
            if not isinstance(part, dict):
                continue
            kind = str(part.get("type") or "")
            if kind in {"reasoning", "thinking", "reasoning_content"}:
                continue
            parts.append(str(part.get("text") or ""))
        return "".join(parts)
    return str(content or "")


def clean_answer_text(message) -> str:
    """Return stripped visible text for an answer message."""
    return extract_visible_text(message).strip()


def chunk_text(message) -> str:
    """Return token delta text for streaming chunks, ignoring tool calls and non-assistant content."""
    kind = getattr(message, "type", "")
    if kind in {"tool", "human", "system"}:
        return ""
    if getattr(message, "tool_call_chunks", None):
        return ""
    return extract_visible_text(message)
