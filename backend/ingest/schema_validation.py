"""Deterministic validation for Schema Architect proposals and user edits."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal
from pydantic import BaseModel, Field

ALLOWED_TYPES = {"text", "integer", "numeric", "date", "boolean"}
ALLOWED_ROLES = {"identifier", "date", "measure", "dimension", "other"}

# Postgres reserved words (common collision list) and reserved system column names
POSTGRES_RESERVED = frozenset(
    {
        "all", "analyse", "analyze", "and", "any", "array", "as", "asc",
        "asymmetric", "both", "case", "cast", "check", "collate", "column",
        "constraint", "create", "current_catalog", "current_date",
        "current_role", "current_time", "current_timestamp", "current_user",
        "default", "deferrable", "desc", "distinct", "do", "else", "end",
        "except", "false", "fetch", "for", "foreign", "from", "grant", "group",
        "having", "in", "initially", "intersect", "into", "lateral", "leading",
        "limit", "localtime", "localtimestamp", "not", "null", "offset", "on",
        "only", "or", "order", "placing", "primary", "references", "returning",
        "select", "session_user", "some", "symmetric", "table", "then", "to",
        "trailing", "true", "union", "unique", "user", "using", "variadic",
        "when", "where", "window", "with",
    }
)

SYSTEM_RESERVED_COLUMNS = frozenset({"workspace_id", "upload_id", "row_id", "id"})

COLUMN_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
TABLE_LABEL_PATTERN = re.compile(r"^[\w\s\-\(\)\.\,\']{1,100}$")


class ValidationIssue(BaseModel):
    level: Literal["error", "warning"]
    field: str | None = None
    column_name: str | None = None
    message: str


class ValidationResult(BaseModel):
    is_valid: bool
    errors: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)

    @property
    def valid(self) -> bool:
        return self.is_valid

    @property
    def error_messages(self) -> list[str]:
        return [e.message for e in self.errors]


def parse_value_as_type(
    val: str,
    target_type: str,
    date_format: str | None = None,
) -> bool:
    """Check if a string value parses cleanly into target_type."""
    if val is None:
        return True
    s = str(val).strip()
    if not s or s.lower() in {"", "null", "none", "nan", "n/a", "na", "\\n"}:
        return True

    if target_type == "text":
        return True

    if target_type == "integer":
        # Reject floats with non-zero decimal part or non-digits (allow commas e.g. 1,000)
        s_clean = s.replace(",", "").replace(" ", "")
        if s_clean.startswith("+") or s_clean.startswith("-"):
            s_num = s_clean[1:]
        else:
            s_num = s_clean
        if not s_num.isdigit():
            # Check if float equivalent to integer e.g. "12.0"
            try:
                dec = Decimal(s_clean)
                return dec == int(dec)
            except InvalidOperation:
                return False
        return True

    if target_type == "numeric":
        s_clean = s.replace(",", "").replace("$", "").replace("€", "").replace("£", "").replace("%", "").strip()
        try:
            Decimal(s_clean)
            return True
        except (InvalidOperation, ValueError):
            return False

    if target_type == "boolean":
        return s.lower() in {"true", "false", "t", "f", "1", "0", "yes", "no", "y", "n"}

    if target_type == "date":
        formats = [date_format] if date_format else ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"]
        for fmt in formats:
            if not fmt:
                continue
            try:
                datetime.strptime(s, fmt)
                return True
            except ValueError:
                continue
        return False

    return False


def check_column_parse_success(
    values: list[str],
    target_type: str,
    date_format: str | None = None,
) -> tuple[float, list[str]]:
    """Compute parse success rate and return sample failures."""
    total = len(values)
    if total == 0:
        return 1.0, []

    success = 0
    failures: list[str] = []
    for val in values:
        if val is None or str(val).strip().lower() in {"", "null", "none", "nan"}:
            success += 1
            continue

        if parse_value_as_type(val, target_type, date_format):
            success += 1
        else:
            if len(failures) < 5 and str(val).strip():
                failures.append(str(val).strip())

    rate = round(success / total, 4)
    return rate, failures


def validate_schema_proposal(
    proposal: dict[str, Any],
    source_columns: list[str] | None = None,
    column_data: dict[str, list[str]] | None = None,
) -> ValidationResult:
    """Deterministic validation of proposal or user-edited schema.

    - Every source column appears exactly once, or is explicitly excluded (when source_columns provided).
    - column_name is valid snake_case identifier, <= 63 chars, not reserved.
    - type and role are in allowed lists.
    - Column count <= 64.
    - table_label and grain are non-empty and sanitized.
    - If column_data is provided, re-verifies type parse success >= 95% for non-text.
    """
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    # 1. Table label validation
    table_label = str(proposal.get("table_label") or "").strip()
    if not table_label:
        errors.append(ValidationIssue(level="error", field="table_label", message="Table label cannot be empty."))
    elif not TABLE_LABEL_PATTERN.match(table_label):
        errors.append(ValidationIssue(level="error", field="table_label", message="Table label contains invalid characters."))

    # 2. Grain validation
    grain = str(proposal.get("grain") or "").strip()
    if not grain:
        errors.append(ValidationIssue(level="error", field="grain", message="Grain string cannot be empty. Please define what one row represents."))

    # 3. Columns validation
    cols = proposal.get("columns") or []
    if not isinstance(cols, list) or len(cols) == 0:
        errors.append(ValidationIssue(level="error", field="columns", message="Schema must define at least one column."))
        return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

    if len(cols) > 64:
        errors.append(ValidationIssue(level="error", field="columns", message="Column count exceeds the maximum limit of 64."))

    source_set = set(source_columns) if source_columns is not None else None
    seen_sources: set[str] = set()
    seen_targets: set[str] = set()

    active_columns = 0

    for idx, col in enumerate(cols):
        if not isinstance(col, dict):
            errors.append(ValidationIssue(level="error", field=f"columns[{idx}]", message="Invalid column format."))
            continue

        source_name = str(col.get("source_name") or "")
        target_name = str(col.get("column_name") or "").strip().lower()
        col_type = str(col.get("type") or "").strip().lower()
        role = str(col.get("role") or "").strip().lower()
        is_excluded = bool(col.get("excluded", False))
        date_format = col.get("date_format")

        # Source name check
        if source_set is not None:
            if not source_name or source_name not in source_set:
                errors.append(
                    ValidationIssue(
                        level="error",
                        field=f"columns[{idx}].source_name",
                        column_name=target_name,
                        message=f"Source column '{source_name}' does not exist in uploaded file.",
                    )
                )
            elif source_name in seen_sources:
                errors.append(
                    ValidationIssue(
                        level="error",
                        field=f"columns[{idx}].source_name",
                        column_name=target_name,
                        message=f"Duplicate mapping for source column '{source_name}'.",
                    )
                )
            else:
                seen_sources.add(source_name)
        else:
            if not source_name:
                errors.append(
                    ValidationIssue(
                        level="error",
                        field=f"columns[{idx}].source_name",
                        column_name=target_name,
                        message="Source column name cannot be empty.",
                    )
                )
            elif source_name in seen_sources:
                errors.append(
                    ValidationIssue(
                        level="error",
                        field=f"columns[{idx}].source_name",
                        column_name=target_name,
                        message=f"Duplicate mapping for source column '{source_name}'.",
                    )
                )
            else:
                seen_sources.add(source_name)

        if is_excluded:
            continue

        active_columns += 1

        # Target name check
        if not target_name:
            errors.append(
                ValidationIssue(
                    level="error",
                    field=f"columns[{idx}].column_name",
                    message="Target column name cannot be empty.",
                )
            )
        elif not COLUMN_NAME_PATTERN.match(target_name):
            errors.append(
                ValidationIssue(
                    level="error",
                    field=f"columns[{idx}].column_name",
                    column_name=target_name,
                    message=f"Target column name '{target_name}' must be snake_case (starts with letter, lowercase letters/digits/underscores, max 63 chars).",
                )
            )
        elif target_name in POSTGRES_RESERVED:
            errors.append(
                ValidationIssue(
                    level="error",
                    field=f"columns[{idx}].column_name",
                    column_name=target_name,
                    message=f"Target column name '{target_name}' is a reserved PostgreSQL keyword.",
                )
            )
        elif target_name in SYSTEM_RESERVED_COLUMNS:
            errors.append(
                ValidationIssue(
                    level="error",
                    field=f"columns[{idx}].column_name",
                    column_name=target_name,
                    message=f"Target column name '{target_name}' is a reserved system column name.",
                )
            )
        elif target_name in seen_targets:
            errors.append(
                ValidationIssue(
                    level="error",
                    field=f"columns[{idx}].column_name",
                    column_name=target_name,
                    message=f"Duplicate target column name '{target_name}'.",
                )
            )
        else:
            seen_targets.add(target_name)

        # Type check
        if col_type not in ALLOWED_TYPES:
            errors.append(
                ValidationIssue(
                    level="error",
                    field=f"columns[{idx}].type",
                    column_name=target_name,
                    message=f"Invalid type '{col_type}'. Allowed types: {sorted(ALLOWED_TYPES)}.",
                )
            )

        # Role check
        if role not in ALLOWED_ROLES:
            warnings.append(
                ValidationIssue(
                    level="warning",
                    field=f"columns[{idx}].role",
                    column_name=target_name,
                    message=f"Unrecognized role '{role}'. Expected one of {sorted(ALLOWED_ROLES)}.",
                )
            )

        # Date format check
        if col_type == "date" and not date_format:
            errors.append(
                ValidationIssue(
                    level="error",
                    field=f"columns[{idx}].date_format",
                    column_name=target_name,
                    message=f"Column '{target_name}' of type 'date' requires a specified date_format.",
                )
            )

        # Server-side full column type re-verification if column data is provided
        if column_data and source_name in column_data and col_type != "text":
            raw_vals = column_data[source_name]
            rate, fails = check_column_parse_success(raw_vals, col_type, date_format)
            if rate < 0.95:
                sample_fails = ", ".join(f"'{f}'" for f in fails[:3])
                errors.append(
                    ValidationIssue(
                        level="error",
                        field=f"columns[{idx}].type",
                        column_name=target_name,
                        message=(
                            f"Type '{col_type}' failed parse verification (success rate {rate * 100:.1f}% < 95%). "
                            f"Failures include: {sample_fails}. Please choose 'text' or fix date format."
                        ),
                    )
                )

    if active_columns == 0:
        errors.append(ValidationIssue(level="error", field="columns", message="At least one column must be included (not excluded)."))

    # Check for missing source columns
    if source_set is not None:
        unmapped = source_set - seen_sources
        if unmapped:
            errors.append(
                ValidationIssue(
                    level="error",
                    field="columns",
                    message=f"Missing source columns from schema: {sorted(unmapped)}. Each source column must appear or be explicitly marked excluded.",
                )
            )

    # Pass through user warnings from proposal
    raw_warnings = proposal.get("warnings") or []
    for w in raw_warnings:
        if isinstance(w, str) and w.strip():
            warnings.append(ValidationIssue(level="warning", message=w.strip()))

    is_valid = len(errors) == 0
    return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)
