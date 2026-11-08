"""Server-Sent Events formatting utilities."""

from __future__ import annotations

import json


def format_sse(event: str, payload: dict) -> str:
    """Format an event name and JSON payload as an SSE text chunk."""
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"

