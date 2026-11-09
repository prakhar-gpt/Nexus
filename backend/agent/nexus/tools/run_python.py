"""run_python tool: sandboxed Python execution for mathematical and comparative calculations."""

from __future__ import annotations

import ast
import csv
import io
import json
import os
import re
import subprocess
import sys
from langchain_core.tools import tool

try:
    from config import settings
    PYTHON_TIMEOUT_SECONDS = settings.NEXUS_TOOL_PYTHON_TIMEOUT_SECONDS
except Exception:
    PYTHON_TIMEOUT_SECONDS = 10

# ---------------------------------------------------------------------------
# Declarative Tool Definition for LangChain / LangGraph
# ---------------------------------------------------------------------------

@tool
def run_python(code: str, inputs: list[str]) -> str:
    """Run deterministic Python (pandas/numpy/math) on prior SQL results.
    MUST be used for all comparisons (comparing regions, segments, categories), differences, percentage changes, ratios, CAGR, and correlations.
    Prior SQL rows are automatically available in a pandas DataFrame named `data`.
    Code must assign a dict named `result` of {label: number}, e.g.
    result = {'difference': round(west - south, 2), 'pct_higher': round(((west - south) / south) * 100, 2)}.
    inputs is ['data'].
    No database access. No network. No file I/O."""


# ---------------------------------------------------------------------------
# Code Pre-Processor & AST Sanitizer
# ---------------------------------------------------------------------------

BLOCKED_NAMES: frozenset[str] = frozenset(
    {
        "open",
        "exec",
        "eval",
        "__import__",
        "compile",
        "breakpoint",
        "input",
        "getattr",
        "setattr",
        "delattr",
        "vars",
        "globals",
        "locals",
        "dir",
    }
)

BLOCKED_MODULES: frozenset[str] = frozenset(
    {
        "os",
        "sys",
        "subprocess",
        "socket",
        "importlib",
        "builtins",
        "ctypes",
        "threading",
        "multiprocessing",
        "pickle",
        "shelve",
        "tempfile",
        "shutil",
        "pathlib",
        "io",
        "signal",
        "resource",
        "mmap",
        "gc",
    }
)

ALLOWED_MODULES: frozenset[str] = frozenset(
    {
        "pandas",
        "numpy",
        "math",
        "statistics",
        "decimal",
        "re",
        "json",
        "datetime",
        "collections",
        "functools",
        "itertools",
        "scipy",
    }
)

_SAFE_BUILTINS: set[str] = {
    "abs", "all", "any", "bool", "dict", "enumerate", "filter", "float",
    "format", "int", "isinstance", "issubclass", "len", "list", "map",
    "max", "min", "print", "range", "round", "set", "slice", "sorted",
    "str", "sum", "tuple", "type", "zip",
}


def clean_code(code: str) -> str:
    """Normalize indentation and strip Markdown fences from LLM-generated code."""
    cleaned = (code or "").strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    try:
        ast.parse(cleaned)
        return cleaned
    except (IndentationError, SyntaxError):
        lines = cleaned.splitlines()
        block_keywords = (
            "def ", "class ", "if ", "elif ", "else:", "for ", "while ",
            "try:", "except", "finally:", "with ", "async "
        )
        has_block = any(l.lstrip().startswith(block_keywords) for l in lines)
        if not has_block:
            flat = "\n".join(l.strip() for l in lines)
            try:
                ast.parse(flat)
                return flat
            except Exception:
                pass
    return cleaned


def _ast_check(code: str) -> str | None:
    """Walk the AST to catch obvious mistakes (subprocess isolation is the real boundary)."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return f"syntax error: {exc}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in BLOCKED_NAMES:
                return f"call to blocked name '{func.id}'"
            if isinstance(func, ast.Attribute) and func.attr in BLOCKED_NAMES:
                return f"call to blocked attr '{func.attr}'"

        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in BLOCKED_MODULES:
                        return f"import of blocked module '{alias.name}'"
            else:
                mod = node.module or ""
                root = mod.split(".")[0]
                if root in BLOCKED_MODULES:
                    return f"import from blocked module '{mod}'"

    return None


def _rows_to_csv(rows: list[dict]) -> str:
    if not rows:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def _build_wrapper(code: str, dataframes: dict[str, list[dict]]) -> str:
    csv_literals: dict[str, str] = {
        name: _rows_to_csv(rows) for name, rows in dataframes.items()
    }
    csv_json = json.dumps(csv_literals)

    wrapper = f"""\
import sys
import io
import json
import math
import statistics
import pandas as _pd

_safe = {{
    name: __builtins__[name]
    for name in {list(_SAFE_BUILTINS)!r}
    if name in __builtins__
}} if isinstance(__builtins__, dict) else {{
    name: getattr(__builtins__, name)
    for name in {list(_SAFE_BUILTINS)!r}
    if hasattr(__builtins__, name)
}}

_csv_data = json.loads({csv_json!r})
_frames = {{}}
for _name, _csv in _csv_data.items():
    if _csv:
        _frames[_name] = _pd.read_csv(io.StringIO(_csv))
    else:
        _frames[_name] = _pd.DataFrame()

if "data" not in _frames:
    _frames["data"] = next(iter(_frames.values())) if _frames else _pd.DataFrame()

_stdout_capture = io.StringIO()
_real_stdout = sys.stdout
sys.stdout = _stdout_capture

_ns = {{
    "__builtins__": _safe,
    "pd": _pd,
    "pandas": _pd,
    "math": math,
    "statistics": statistics,
    "result": {{}},
    **_frames,
}}

try:
    exec(compile({code!r}, "<user_code>", "exec"), _ns)
except Exception as _exc:
    sys.stdout = _real_stdout
    print("NEXUS_RESULT:" + json.dumps({{"ok": False, "error": str(_exc)}}))
    sys.exit(1)

sys.stdout = _real_stdout
_captured = _stdout_capture.getvalue()

_result = _ns.get("result", {{}})
if not isinstance(_result, dict):
    print(_captured, end="")
    print("NEXUS_RESULT:" + json.dumps({{"ok": False, "error": "result must be a dict"}}))
    sys.exit(1)

_bad = []
_cleaned_result = {{}}
for _k, _v in _result.items():
    if hasattr(_v, "item"):
        _v = _v.item()
    if isinstance(_v, (int, float)):
        _cleaned_result[str(_k)] = round(float(_v), 4) if isinstance(_v, float) else int(_v)
    elif isinstance(_v, (str, bool)):
        _cleaned_result[str(_k)] = _v
    else:
        try:
            _cleaned_result[str(_k)] = float(_v)
        except Exception:
            _bad.append(_k)

if _bad:
    print(_captured, end="")
    print("NEXUS_RESULT:" + json.dumps({{"ok": False, "error": f"non-numeric values in result: {{_bad}}"}}))
    sys.exit(1)

_vars = {{}}
for _k, _v in _ns.items():
    if _k.startswith("_") or _k in ("pd", "pandas", "math", "statistics", "data", "result", "json", "sys", "io"):
        continue
    if hasattr(_v, "item"):
        _v = _v.item()
    if isinstance(_v, (int, float)):
        _vars[str(_k)] = round(float(_v), 4) if isinstance(_v, float) else int(_v)
    elif isinstance(_v, (str, bool)):
        _vars[str(_k)] = str(_v)[:100]

print(_captured, end="")
print("NEXUS_RESULT:" + json.dumps({{"ok": True, "result": _cleaned_result, "variables": _vars}}))
"""
    return wrapper


def execute_sandboxed(code: str, dataframes: dict[str, list[dict]]) -> dict:
    """Execute code in a sandboxed subprocess with no DB credentials."""
    code = clean_code(code)

    reason = _ast_check(code)
    if reason:
        return {
            "ok": False,
            "results": {},
            "stdout_truncated": "",
            "error": f"blocked: {reason}",
        }

    wrapper = _build_wrapper(code, dataframes)
    scrubbed_env = {
        "PATH": os.environ.get("PATH", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
    }

    try:
        proc = subprocess.run(
            [sys.executable, "-c", wrapper],
            timeout=PYTHON_TIMEOUT_SECONDS,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=scrubbed_env,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "results": {},
            "stdout_truncated": "",
            "error": f"execution timed out after {PYTHON_TIMEOUT_SECONDS}s",
        }

    if proc.returncode != 0:
        return {
            "ok": False,
            "results": {},
            "stdout_truncated": proc.stderr[:500],
            "error": "execution failed",
        }

    stdout_lines = proc.stdout.splitlines()
    result_line = None
    pre_lines: list[str] = []

    for line in stdout_lines:
        if line.startswith("NEXUS_RESULT:"):
            result_line = line[len("NEXUS_RESULT:"):]
        else:
            pre_lines.append(line)

    captured_stdout = "\n".join(pre_lines)[:2000]

    if result_line is None:
        return {
            "ok": False,
            "results": {},
            "stdout_truncated": captured_stdout,
            "error": "no NEXUS_RESULT line found in output",
        }

    try:
        payload = json.loads(result_line)
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "results": {},
            "stdout_truncated": captured_stdout,
            "error": f"could not parse NEXUS_RESULT JSON: {exc}",
        }

    if not payload.get("ok"):
        return {
            "ok": False,
            "results": {},
            "stdout_truncated": captured_stdout,
            "error": payload.get("error", "unknown error"),
        }

    result_dict: dict = payload.get("result", {})
    bad_keys = []
    cleaned_dict = {}
    for k, v in result_dict.items():
        if isinstance(v, (int, float)):
            cleaned_dict[k] = v
        elif isinstance(v, str):
            try:
                cleaned_dict[k] = float(v)
            except ValueError:
                cleaned_dict[k] = v
        else:
            bad_keys.append(k)

    if bad_keys:
        return {
            "ok": False,
            "results": {},
            "stdout_truncated": captured_stdout,
            "error": f"non-numeric values in result: {bad_keys}",
        }

    return {
        "ok": True,
        "results": cleaned_dict,
        "variables": payload.get("variables", {}),
        "stdout_truncated": captured_stdout,
        "error": None,
    }


class PythonExecutionResult(tuple):
    """2-tuple (summary, results) with .variables metadata for backward compatibility."""

    def __new__(cls, summary: str, results: dict, variables: dict | None = None):
        obj = super().__new__(cls, (summary, results))
        obj.summary = summary
        obj.results = results
        obj.variables = variables or {}
        return obj


def execute_python(
    code: str,
    inputs: list[str] | None = None,
    rows: list[dict] | None = None,
    sql_results: dict[str, list[dict]] | None = None,
) -> PythonExecutionResult:
    """Execute sandboxed Python with multiple DataFrame support and token safety."""
    dataframes: dict[str, list[dict]] = {}
    inputs = list(inputs or [])
    sql_results = sql_results or {}
    rows = rows or []

    for inp in inputs:
        clean_name = re.sub(r"[^a-zA-Z0-9_]", "_", str(inp).strip())
        if inp in sql_results and sql_results[inp]:
            dataframes[clean_name] = sql_results[inp]
        elif clean_name in sql_results and sql_results[clean_name]:
            dataframes[clean_name] = sql_results[clean_name]

    if not dataframes and rows:
        dataframes["data"] = rows
    elif rows and "data" not in dataframes:
        dataframes["data"] = rows

    for k, v in sql_results.items():
        clean_k = re.sub(r"[^a-zA-Z0-9_]", "_", k)
        if clean_k not in dataframes and v:
            dataframes[clean_k] = v

    total_rows = sum(len(v) for v in dataframes.values())
    if total_rows == 0:
        return PythonExecutionResult(
            "rejected: No SQL query data is available in this turn yet. "
            "You must first run run_sql to retrieve the required data before calling run_python.",
            {},
            {},
        )

    result = execute_sandboxed(code, dataframes)

    if not result["ok"]:
        return PythonExecutionResult(f"rejected: {result['error']}", {}, {})

    parts = ", ".join(f"{k}={v}" for k, v in result["results"].items())
    summary = f"result: {parts}" if parts else "result: (empty)"
    return PythonExecutionResult(summary, result["results"], result.get("variables", {}))
