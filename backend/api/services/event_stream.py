"""Server-Sent Events streaming logic for file upload and ingestion progress."""

from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator

from utils import format_sse


async def stream_upload_events(
    upload_id: str,
    since_seq: int = 0,
    max_ticks: int = 300,
) -> AsyncGenerator[str, None]:
    """Yield Server-Sent Events tracking ingestion progress with replay and keepalive."""
    from api.services.upload_service import fetch_upload_events_from_db

    last_seq = int(since_seq)
    ticks = 0

    while ticks < max_ticks:
        events = fetch_upload_events_from_db(upload_id, since_seq=last_seq)
        if events:
            for item in events:
                seq = item.get("seq", last_seq + 1)
                last_seq = max(last_seq, seq)
                event_name = item.get("event", "step")
                raw_data = json.dumps(item)
                yield f"id: {seq}\nevent: {event_name}\ndata: {raw_data}\n\n"

                if event_name in {"done", "error"} or item.get("final") in {
                    "loaded",
                    "rejected",
                    "needs_schema_review",
                    "needs_confirmation",
                }:
                    if item.get("stage") != "propose" or event_name == "done":
                        if event_name in {"done", "error"}:
                            return

        await asyncio.sleep(0.5)
        ticks += 1
        if ticks % 10 == 0:
            yield ": keepalive\n\n"

    yield format_sse("error", {"message": "ingest stream timed out"})
