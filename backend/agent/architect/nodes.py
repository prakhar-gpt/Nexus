"""Schema Architect LangGraph execution nodes."""

from __future__ import annotations

import json
from typing import Any
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

from agent.architect.models import ColumnProposal, SchemaProposal
from agent.architect.state import ArchitectState, MAX_ARCHITECT_STEPS
from agent.architect.tools.check_uniqueness import execute_check_uniqueness
from agent.architect.tools.detect_date_format import execute_detect_date_format
from agent.architect.tools.list_columns import execute_list_columns
from agent.architect.tools.profile_column import execute_profile_column
from agent.architect.tools.sample_rows import execute_sample_rows
from agent.architect.tools.test_parse import execute_test_parse


def fallback_proposal_from_df(
    df,
    table_label: str = "Custom Dataset",
    user_hint: str | None = None,
) -> SchemaProposal:
    """Deterministic fallback proposal if LLM fails or hits step limit."""
    cols_meta = execute_list_columns(df).get("columns", [])
    columns: list[ColumnProposal] = []
    warnings: list[str] = []

    for col_info in cols_meta:
        src = col_info["source_name"]
        prof = execute_profile_column(df, src)
        null_rate = prof.get("null_rate", 0.0)
        has_zeros = prof.get("has_leading_zero_ids", False)

        snake = src.lower().replace(" ", "_").replace("-", "_")
        snake = "".join(c for c in snake if c.isalnum() or c == "_")
        if not snake or not snake[0].isalpha():
            snake = f"col_{snake}"
        snake = snake[:63]
        if snake in {"row_id", "upload_id", "workspace_id", "id"}:
            snake = f"src_{snake}"

        is_id_like = any(term in snake for term in ("id", "code", "zip", "postal", "phone", "fax", "ssn", "ein", "nbr", "key"))

        if has_zeros or (is_id_like and any(term in snake for term in ("zip", "postal", "code", "phone"))):
            chosen_type = "text"
            role = "identifier"
            dt_fmt = None
            rate = 1.0
        else:
            dt_prof = execute_detect_date_format(df, src)
            cand_fmts = dt_prof.get("candidate_formats", [])
            if cand_fmts and cand_fmts[0]["rate"] >= 0.90:
                chosen_type = "date"
                role = "date"
                dt_fmt = cand_fmts[0]["format"]
                rate = cand_fmts[0]["rate"]
                if dt_prof.get("ambiguous_day_month"):
                    warnings.append(f"Column '{src}' has ambiguous day/month ordering.")
            else:
                p_int = execute_test_parse(df, src, "integer")
                if p_int.get("parse_success_rate", 0) >= 0.95:
                    chosen_type = "integer"
                    role = "identifier" if is_id_like else "measure"
                    dt_fmt = None
                    rate = p_int["parse_success_rate"]
                else:
                    p_num = execute_test_parse(df, src, "numeric")
                    if p_num.get("parse_success_rate", 0) >= 0.95:
                        chosen_type = "numeric"
                        role = "identifier" if is_id_like else "measure"
                        dt_fmt = None
                        rate = p_num["parse_success_rate"]
                    else:
                        chosen_type = "text"
                        role = "identifier" if is_id_like else "dimension"
                        dt_fmt = None
                        rate = 1.0

        columns.append(
            ColumnProposal(
                source_name=src,
                column_name=snake,
                type=chosen_type,
                role=role,
                description=f"Values from '{src}'",
                unit=None,
                nullable=null_rate > 0,
                date_format=dt_fmt,
                parse_success_rate=rate,
                confidence=0.85,
                notes=None,
            )
        )

    grain_desc = f"One row of {table_label.lower()} data"
    if user_hint:
        grain_desc += f" ({user_hint})"

    return SchemaProposal(
        table_label=table_label,
        grain=grain_desc,
        grain_key_columns=[],
        columns=columns,
        warnings=warnings,
        analysis_hints=["Review column types and date formats before loading."],
    )


def architect_agent_node(
    state: ArchitectState,
    model,
    system_prompt: str,
    tools: list,
) -> dict[str, Any]:
    """Call the LLM with tool binding if within step limit."""
    step_count = state.get("step_count", 0)
    messages = list(state.get("messages") or [])
    allowed = step_count < MAX_ARCHITECT_STEPS

    chat = model.bind_tools(tools) if allowed else model
    try:
        response = chat.invoke([SystemMessage(content=system_prompt), *messages])
    except Exception as exc:
        response = AIMessage(content=f"Model error: {exc}")

    return {
        "messages": [response],
        "step_count": step_count + 1,
    }


def architect_tools_node(state: ArchitectState, tools_map: dict[str, Any], progress_callback=None) -> dict[str, Any]:
    """Execute tool calls and record audit trail."""
    messages = list(state.get("messages") or [])
    last = messages[-1] if messages else None
    tool_calls = getattr(last, "tool_calls", None) or []
    tool_records = list(state.get("tool_calls_record") or [])

    tool_messages = []
    for tc in tool_calls:
        name = tc.get("name")
        args = tc.get("args") or {}
        call_id = tc.get("id")

        tool_fn = tools_map.get(name)
        if tool_fn:
            try:
                output = tool_fn.invoke(args)
            except Exception as e:
                output = {"error": str(e)}
        else:
            output = {"error": f"Tool '{name}' not found"}

        record = {
            "step": state.get("step_count", 1),
            "tool": name,
            "args": args,
            "summary": str(output)[:120],
        }
        tool_records.append(record)
        if progress_callback:
            progress_callback({
                "event": "architect_tool",
                **record,
            })

        tool_messages.append(
            ToolMessage(content=json.dumps(output, default=str), tool_call_id=call_id)
        )

    return {
        "messages": tool_messages,
        "tool_calls_record": tool_records,
    }


def route_architect_next_step(state: ArchitectState) -> str:
    """Route to 'tools' if tool calls requested and under step cap, else END."""
    messages = list(state.get("messages") or [])
    last = messages[-1] if messages else None
    tool_calls = getattr(last, "tool_calls", None)
    if tool_calls and state.get("step_count", 0) < MAX_ARCHITECT_STEPS:
        return "tools"
    return "finalize"

