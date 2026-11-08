"""Sandboxed Python execution for run_python tool.

Security boundary: subprocess with scrubbed environment and no DB credentials.
The AST check below is NOT the security boundary — it is a second layer to catch
obvious mistakes early. The real boundary is the subprocess isolation.
"""

from __future__ import annotations

import ast
import csv
import io
import json
import os
import subprocess
import sys
import textwrap

# ---------------------------------------------------------------------------
# Block-lists for the AST pre-check (second layer, not the security boundary)
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

# ---------------------------------------------------------------------------
# AST check — catches obvious mistakes. It is NOT the security boundary.
# ---------------------------------------------------------------------------


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
    """Walk the AST and return a reason string if the code is blocked, else None.

    # AST check catches obvious mistakes. It is NOT the security boundary.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return f"syntax error: {exc}"

    for node in ast.walk(tree):
        # Block calls to dangerous builtins / names
        if isinstance(node, ast.Call):
            func = node.func
            # func could be ast.Name or ast.Attribute
            if isinstance(func, ast.Name) and func.id in BLOCKED_NAMES:
                return f"call to blocked name '{func.id}'"
            if isinstance(func, ast.Attribute) and func.attr in BLOCKED_NAMES:
                return f"call to blocked attr '{func.attr}'"

        # Block top-level and inline imports from blocked modules
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in BLOCKED_MODULES:
                        return f"import of blocked module '{alias.name}'"
            else:
                # ast.ImportFrom
                mod = node.module or ""
                root = mod.split(".")[0]
                if root in BLOCKED_MODULES:
                    return f"import from blocked module '{mod}'"

    return None


# ---------------------------------------------------------------------------
# CSV serialiser
# ---------------------------------------------------------------------------


def _rows_to_csv(rows: list[dict]) -> str:
    """Serialise a list-of-dicts to a CSV string."""
    if not rows:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Wrapper script builder
# ---------------------------------------------------------------------------


def _build_wrapper(code: str, dataframes: dict[str, list[dict]]) -> str:
    """Return a self-contained Python script string that runs `code` sandboxed."""

    # Serialise each dataframe to a CSV literal embedded in the script
    csv_literals: dict[str, str] = {
        name: _rows_to_csv(rows) for name, rows in dataframes.items()
    }

    # Encode CSV data as JSON so it embeds safely in the script
    csv_json = json.dumps(csv_literals)

    # The user code is embedded as a raw string to avoid quoting issues
    user_code_lines = textwrap.indent(code, "    ")

    wrapper = f"""\
import sys
import io
import json
import math
import statistics
import pandas as _pd

# Restrict builtins to a safe subset
_safe = {{
    name: __builtins__[name]
    for name in {list(_SAFE_BUILTINS)!r}
    if name in __builtins__
}} if isinstance(__builtins__, dict) else {{
    name: getattr(__builtins__, name)
    for name in {list(_SAFE_BUILTINS)!r}
    if hasattr(__builtins__, name)
}}

# Load dataframes from embedded CSV data
_csv_data = json.loads({csv_json!r})
_frames = {{}}
for _name, _csv in _csv_data.items():
    if _csv:
        _frames[_name] = _pd.read_csv(io.StringIO(_csv))
    else:
        _frames[_name] = _pd.DataFrame()

# Ensure 'data' is always defined
if "data" not in _frames:
    _frames["data"] = next(iter(_frames.values())) if _frames else _pd.DataFrame()

# Redirect stdout to capture print() calls
_stdout_capture = io.StringIO()
_real_stdout = sys.stdout
sys.stdout = _stdout_capture

# Execute user code in a restricted namespace
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

# Validate and normalize numeric values
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

print(_captured, end="")
print("NEXUS_RESULT:" + json.dumps({{"ok": True, "result": _cleaned_result}}))
"""
    return wrapper


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def execute_sandboxed(
    code: str,
    dataframes: dict[str, list[dict]],
) -> dict:
    """Execute `code` in a sandboxed subprocess with no DB credentials.

    Parameters
    ----------
    code:
        Python source assigned by the LLM.  Must assign a dict called ``result``
        whose values are all int or float.
    dataframes:
        Mapping of alias → list-of-dicts.  Each entry is exposed to the
        sandboxed script as a ``pandas.DataFrame`` variable with that name.

    Returns
    -------
    dict with keys:
        ok              – bool
        results         – dict[str, int|float] on success, else {}
        stdout_truncated – captured print() output (max 2000 chars)
        error           – error message or None
    """
    code = clean_code(code)

    # -- Second-layer AST check (NOT the security boundary) ------------------
    reason = _ast_check(code)
    if reason:
        return {
            "ok": False,
            "results": {},
            "stdout_truncated": "",
            "error": f"blocked: {reason}",
        }

    # -- Build and run the subprocess ----------------------------------------
    wrapper = _build_wrapper(code, dataframes)

    # Scrubbed environment: no credentials, no API keys — only PATH / SYSTEMROOT
    scrubbed_env = {
        "PATH": os.environ.get("PATH", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
    }

    try:
        proc = subprocess.run(
            [sys.executable, "-c", wrapper],
            timeout=10,
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
            "error": "execution timed out after 10s",
        }

    if proc.returncode != 0:
        return {
            "ok": False,
            "results": {},
            "stdout_truncated": proc.stderr[:500],
            "error": "execution failed",
        }

    # -- Parse output --------------------------------------------------------
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
        "stdout_truncated": captured_stdout,
        "error": None,
    }


# ---------------------------------------------------------------------------
# Attack tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import textwrap as _tw

    _PASS = "\033[92mPASS\033[0m"
    _FAIL = "\033[91mFAIL\033[0m"

    def _check(label: str, r: dict, expect_ok: bool, *, extra: str = "") -> None:  # noqa: ANN001
        ok = r["ok"] == expect_ok
        marker = _PASS if ok else _FAIL
        print(f"{marker}  {label}")
        if extra:
            print(f"       {extra}: {r}")
        if not ok:
            print(f"       got: {r}")

    # 1. import os → AST blocks it
    r = execute_sandboxed("import os", {})
    _check("import os blocked by AST", r, expect_ok=False)
    assert "blocked" in r["error"], r

    # 2. open('/etc/passwd') → AST blocks it
    r = execute_sandboxed("open('/etc/passwd')", {})
    _check("open() blocked by AST", r, expect_ok=False)
    assert "blocked" in r["error"], r

    # 3. infinite loop → timeout
    r = execute_sandboxed("while True: pass", {})
    _check("infinite loop times out", r, expect_ok=False)
    assert "timed out" in r["error"], r

    # 4. memory bomb → timeout / killed within 10 s
    r = execute_sandboxed("x = [0]*10**9", {})
    _check("memory bomb times out or killed", r, expect_ok=False)
    # either timed out or execution failed (OOM kill)
    assert r["error"] in ("execution timed out after 10s", "execution failed"), r

    # 5. socket connect → AST blocks it
    r = execute_sandboxed("import socket; socket.connect(('1.2.3.4', 80))", {})
    _check("socket import blocked by AST", r, expect_ok=False)
    assert "blocked" in r["error"], r

    # 6. PGPASSWORD exfiltration → AST blocks import os
    r = execute_sandboxed("import os; os.environ['PGPASSWORD']", {})
    _check("import os for PGPASSWORD blocked by AST", r, expect_ok=False)
    assert "blocked" in r["error"], r

    # 7. Valid CAGR calculation — should succeed
    cagr_code = "result = {\"cagr\": round((500/100)**(1/4)-1, 4)}"
    r = execute_sandboxed(cagr_code, {})
    _check("valid CAGR calculation ok", r, expect_ok=True)
    assert r["ok"], r
    assert abs(r["results"]["cagr"] - 0.4953) < 0.001, r
    print(f"       cagr value: {r['results']['cagr']}")

    print("\nAll attack tests passed.")
