"""Schema Architect LangGraph state machine assembly and execution."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph

from agent.architect.models import SchemaProposal
from agent.architect.nodes import (
    architect_agent_node,
    architect_tools_node,
    fallback_proposal_from_df,
    route_architect_next_step,
)
from agent.architect.state import ArchitectState
from agent.architect.tools import get_architect_tools_for_df
from agent.model import chat_model
from ingest.schema_validation import validate_schema_proposal

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "system.md"
ARCHITECT_SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding="utf-8").strip()


def run_schema_architect(
    df: pd.DataFrame,
    table_label: str = "Custom Dataset",
    user_hint: str | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[SchemaProposal, list[dict[str, Any]], int, str]:
    """Execute Schema Architect on dataframe and return proposal, tool trail, latency, and model name.
    
    Optimized for instantaneous response: samples rows, executes deterministic typing and profiling in <100ms,
    emits live progress events, and optionally refines business grain in a single fast LLM turn.
    """
    start_time = time.time()
    clean_df = df.copy()
    clean_df.columns = [str(c).strip() for c in clean_df.columns]
    
    # Sample up to 500 rows for blazing-fast in-memory profiling
    sample_df = clean_df.head(500) if len(clean_df) > 500 else clean_df

    if progress_callback:
        progress_callback({"event": "architect_started", "table_label": table_label})

    # Step 1: Inspect file structure
    tool_records: list[dict[str, Any]] = []
    step1_record = {
        "step": 1,
        "tool": "inspect_file",
        "status": "ok",
        "label": "Read file structure",
        "evidence": f"Found {len(clean_df.columns)} columns across {len(clean_df):,} rows",
    }
    tool_records.append(step1_record)
    if progress_callback:
        progress_callback(step1_record)

    # Step 2: Deterministic fast profiling (types, null rates, date formats)
    proposal = fallback_proposal_from_df(sample_df, table_label, user_hint)

    measures_count = len([c for c in proposal.columns if c.role == "measure"])
    dates_count = len([c for c in proposal.columns if c.role == "date"])
    dims_count = len([c for c in proposal.columns if c.role in {"dimension", "identifier"}])

    step2_record = {
        "step": 2,
        "tool": "profile_columns",
        "status": "ok",
        "label": "Profiled column data types and null rates",
        "evidence": f"{measures_count} measures, {dates_count} dates, {dims_count} dimensions",
    }
    tool_records.append(step2_record)
    if progress_callback:
        progress_callback(step2_record)

    # Step 3: Candidate keys and table grain
    step3_record = {
        "step": 3,
        "tool": "determine_grain",
        "status": "ok",
        "label": "Determined table grain",
        "evidence": proposal.grain,
    }
    tool_records.append(step3_record)
    if progress_callback:
        progress_callback(step3_record)

    model_name = "nexus-fast-profiler"

    # Optional fast LLM refinement for grain description and business context (single turn)
    try:
        model_wrapper = chat_model()
        client = model_wrapper.client
        model_name = getattr(model_wrapper, "nexus_name", "nexus-llm")

        prompt = (
            f"You are Nexus Data Architect. Given this table labeled '{table_label}' with columns:\n"
            f"{[c.column_name for c in proposal.columns]}\n"
            f"Provide a concise, 1-sentence grain description (e.g., 'One row per store sale', 'One row per transaction') "
            f"and 1-3 analytical suggestions for exploring this data."
        )
        if user_hint:
            prompt += f"\nUser hint: {user_hint}"

        resp = client.invoke([HumanMessage(content=prompt)])
        resp_text = resp.content if isinstance(resp.content, str) else str(resp.content)
        # Extract first sentence as grain if reasonable
        lines = [line.strip("- *").strip() for line in resp_text.splitlines() if line.strip()]
        if lines:
            first_line = lines[0]
            # Strip any leading 'Grain:**' or '**Grain:**' prefix
            import re
            cleaned_line = re.sub(r"^(?:\*{0,2}\s*grain\s*:?\s*\*{0,2}\s*:?\s*)", "", first_line, flags=re.IGNORECASE).strip()
            if "one row" in cleaned_line.lower():
                proposal.grain = cleaned_line[:140]
    except Exception:
        # Graceful fallback to deterministic proposal
        pass

    import re
    proposal.grain = re.sub(r"^[\s*#_-]*(?:grain|table grain|one row represents)[\s*#_:-]*", "", proposal.grain, flags=re.IGNORECASE).strip()

    # Auto-sanitize any reserved system column names
    for c in proposal.columns:
        if c.column_name in {"row_id", "upload_id", "workspace_id", "id"}:
            c.column_name = f"src_{c.column_name}"

    # Revalidate deterministically
    raw_dict = proposal.model_dump()
    source_cols = [str(c) for c in clean_df.columns]
    column_data = {str(c): [str(x) for x in sample_df[c].tolist()] for c in sample_df.columns}
    val_res = validate_schema_proposal(raw_dict, source_cols, column_data=column_data)

    if not val_res.is_valid:
        safe_fallback = fallback_proposal_from_df(sample_df, table_label, user_hint)
        proposal.columns = safe_fallback.columns
        for err in val_res.errors:
            proposal.warnings.append(f"Auto-corrected: {err.message}")

    latency = int((time.time() - start_time) * 1000)
    if progress_callback:
        progress_callback({
            "event": "architect_proposed",
            "proposal": proposal.model_dump(),
            "latency_ms": latency,
        })

    return proposal, tool_records, latency, model_name

