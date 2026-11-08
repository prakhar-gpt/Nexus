"""Map source headers onto sales_clean columns."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

CANONICAL = (
    "order_date",
    "customer_id",
    "product_id",
    "quantity",
    "revenue",
    "unit_price",
    "discount_pct",
    "cost",
    "profit",
    "segment",
    "region",
    "category",
    "sub_category",
    "channel",
)
AUTO_THRESHOLD = 70
HINTS_PATH = Path(__file__).resolve().parents[1] / "kb" / "column_hints.md"
_HINT_ROW = re.compile(r"^\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*$")

# Standard commercial retail synonyms auto-accepted without confirmation.
SYNONYMS: dict[str, str] = {
    "sales": "revenue",
    "turnover": "revenue",
    "gross sales": "revenue",
    "net sales": "revenue",
    "total sales": "revenue",
}

# Minimum confidence returned by the LLM to auto-accept (without confirmation).
LLM_AUTO_THRESHOLD = 70


@dataclass
class Proposal:
    source: str
    canonical: str | None
    confidence: float
    method: str
    needs_confirmation: bool
    confirmed_by_user: bool = False


def normalize(value: str) -> str:
    text = value.lower().replace("_", " ").replace("-", " ")
    return " ".join(text.split())


def normalize_to_snake(header: str) -> str:
    """Lowercase, replace spaces/hyphens with underscores, strip non-alphanumeric except underscore."""
    text = header.lower()
    text = re.sub(r"[ \-]+", "_", text)
    text = re.sub(r"[^a-z0-9_]", "", text)
    return text


def load_hints(path: Path = HINTS_PATH) -> dict[str, str]:
    hints = {}
    if not path.exists():
        return hints
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _HINT_ROW.match(line.strip())
        if not match:
            continue
        source, canonical = match.group(1), match.group(2)
        if source.lower() == "source header" or set(source) <= {"-"}:
            continue
        if canonical in CANONICAL:
            hints[normalize(source)] = canonical
    return hints


def best_score(header: str) -> tuple[float, str]:
    folded = normalize(header)
    scored = [
        (fuzz.ratio(folded, normalize(name)), name) for name in CANONICAL
    ]
    return max(scored)


def _llm_propose(
    header: str,
    sample_values: list[str],
) -> tuple[str | None, float] | None:
    """Ask the LLM to map a single header to a canonical column.

    Returns (canonical_or_None, confidence) or None on failure.
    """
    try:
        from agent.model import ModelError, resolve
        from langchain_openai import ChatOpenAI

        label, secret, base_url, model_name = resolve()
    except Exception:  # noqa: BLE001
        return None

    samples_part = ", ".join(repr(v) for v in sample_values[:5]) if sample_values else "(no samples)"
    prompt = (
        f"Header: {json.dumps(header)}\n"
        f"Sample values: {samples_part}\n"
        f"Canonical columns: {', '.join(CANONICAL)}\n\n"
        "Respond with ONLY a JSON object on one line:\n"
        '{"source_column": "<header>", "canonical_column": "<canonical or null>", "confidence": <0.0-1.0>}'
    )
    try:
        from langchain_openai import ChatOpenAI

        client = ChatOpenAI(
            api_key=secret,
            base_url=base_url,
            model=model_name,
            streaming=False,
            temperature=0,
            max_tokens=120,
        )
        response = client.invoke(prompt)
        content = response.content.strip()
        # Extract the JSON — model may add markdown fences
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if not json_match:
            return None
        data = json.loads(json_match.group())
        canonical = data.get("canonical_column") or None
        # Confidence may be 0–1 or 0–100; normalise to 0–100
        raw_conf = float(data.get("confidence", 0))
        confidence = raw_conf * 100 if raw_conf <= 1.0 else raw_conf
        if canonical not in CANONICAL:
            canonical = None
        return canonical, confidence
    except Exception:  # noqa: BLE001
        logger.debug("LLM proposal failed for header %r", header, exc_info=True)
        return None


def propose_columns(
    headers: list[str],
    hints: dict[str, str] | None = None,
    samples: dict[str, list[str]] | None = None,
) -> list[Proposal]:
    """Propose canonical mappings for each source header.

    Parameters
    ----------
    headers:
        Source column names as read from the uploaded file.
    hints:
        Pre-loaded column hints (loaded from column_hints.md if None).
    samples:
        Optional dict mapping header → list of up to 5 sample values.
        When provided and an LLM key is available, columns that fall below
        AUTO_THRESHOLD and are not covered by hints are sent to the LLM for
        an additional proposal.  Results below LLM_AUTO_THRESHOLD always
        require user confirmation.
    """
    hints = load_hints() if hints is None else hints
    proposals = []
    used = set()
    ranked = []
    for header in headers:
        score, name = best_score(header)
        ranked.append((score, header, name))
    for score, header, name in sorted(ranked, reverse=True):
        norm_header = normalize(header)
        syn = SYNONYMS.get(norm_header)
        if syn and syn not in used:
            used.add(syn)
            proposals.append(
                Proposal(header, syn, 100.0, "fuzzy", needs_confirmation=False)
            )
            continue
        hinted = hints.get(norm_header)
        if score >= AUTO_THRESHOLD and name not in used:
            used.add(name)
            proposals.append(
                Proposal(header, name, score, "fuzzy", needs_confirmation=False)
            )
            continue
        if hinted and hinted not in used:
            used.add(hinted)
            proposals.append(
                Proposal(header, hinted, score, "llm", needs_confirmation=True)
            )
            continue
        # Below threshold and not in hints — try the LLM if samples provided
        if samples is not None:
            llm_result = _llm_propose(header, samples.get(header, []))
            if llm_result is not None:
                llm_canonical, llm_confidence = llm_result
                if llm_canonical and llm_canonical not in used and llm_confidence >= LLM_AUTO_THRESHOLD:
                    # Still require confirmation even above threshold (per spec)
                    used.add(llm_canonical)
                    proposals.append(
                        Proposal(
                            header,
                            llm_canonical,
                            llm_confidence,
                            "llm",
                            needs_confirmation=True,
                        )
                    )
                    continue
        proposals.append(Proposal(header, None, score, "fuzzy", False))
    by_source = {proposal.source: proposal for proposal in proposals}
    return [by_source[header] for header in headers]


def domain_gap(columns: set[str]) -> str | None:
    missing = []
    if "order_date" not in columns:
        missing.append("a date")
    if "customer_id" not in columns and "product_id" not in columns:
        missing.append("a customer or product identifier")
    if "revenue" not in columns and "quantity" not in columns:
        missing.append("revenue or quantity")
    if not missing:
        return None
    return "missing " + ", ".join(missing)


def compute_capabilities(cleaned_rows: list[dict]) -> dict:
    """Return a capabilities dict from a list of cleaned row dicts."""
    populated: set[str] = set()
    order_dates: list[str] = []

    for row in cleaned_rows:
        for key, value in row.items():
            if value is not None and str(value).strip() != "":
                populated.add(key)
        if row.get("order_date"):
            order_dates.append(str(row["order_date"]))

    return capabilities_from_attribute_schema(populated, order_dates)


def capabilities_from_attribute_schema(
    canonical_populated: set[str],
    order_dates: list[str],
) -> dict:
    """Compute analytical capabilities (revenue, trend, margin, discount, customer) and reasons."""
    has_revenue = "revenue" in canonical_populated

    distinct_years: set[str] = set()
    for date_str in order_dates:
        try:
            year = str(date_str).split("-")[0]
            if year:
                distinct_years.add(year)
        except Exception:
            pass
    has_trend = len(distinct_years) >= 2
    has_margin = "cost" in canonical_populated or "profit" in canonical_populated
    has_discount = "discount_pct" in canonical_populated
    has_customer = "customer_id" in canonical_populated

    reasons: dict[str, str] = {}
    if not has_revenue:
        reasons["revenue"] = "revenue column is absent"
    if not has_trend:
        if "order_date" not in canonical_populated:
            reasons["trend"] = "order_date column is absent"
        else:
            reasons["trend"] = (
                f"order_date has only {len(distinct_years)} distinct "
                f"year{'s' if len(distinct_years) != 1 else ''} "
                "(need at least 2 for trend analysis)"
            )
    if not has_margin:
        reasons["margin"] = "cost and profit are both absent"
    if not has_discount:
        reasons["discount"] = "discount_pct column is absent"
    if not has_customer:
        reasons["customer"] = "customer_id column is absent"

    return {
        "revenue": has_revenue,
        "trend": has_trend,
        "margin": has_margin,
        "discount": has_discount,
        "customer": has_customer,
        "reasons": reasons,
    }
