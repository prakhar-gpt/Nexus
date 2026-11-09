"""Architect profiling tools package exports."""

from __future__ import annotations

from agent.architect.tools.check_uniqueness import execute_check_uniqueness, make_check_uniqueness_tool
from agent.architect.tools.detect_date_format import execute_detect_date_format, make_detect_date_format_tool
from agent.architect.tools.list_columns import execute_list_columns, make_list_columns_tool
from agent.architect.tools.profile_column import execute_profile_column, make_profile_column_tool
from agent.architect.tools.sample_rows import execute_sample_rows, make_sample_rows_tool
from agent.architect.tools.test_parse import execute_test_parse, make_test_parse_tool


def get_architect_tools_for_df(df):
    """Return the 6 bound profiling tools for an uploaded dataframe."""
    return [
        make_list_columns_tool(df),
        make_profile_column_tool(df),
        make_sample_rows_tool(df),
        make_test_parse_tool(df),
        make_detect_date_format_tool(df),
        make_check_uniqueness_tool(df),
    ]


__all__ = [
    "get_architect_tools_for_df",
    "execute_list_columns",
    "make_list_columns_tool",
    "execute_profile_column",
    "make_profile_column_tool",
    "execute_sample_rows",
    "make_sample_rows_tool",
    "execute_test_parse",
    "make_test_parse_tool",
    "execute_detect_date_format",
    "make_detect_date_format_tool",
    "execute_check_uniqueness",
    "make_check_uniqueness_tool",
]

