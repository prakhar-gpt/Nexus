"""Compute which analytical capabilities are available for a given upload."""

from __future__ import annotations


def compute_capabilities(cleaned_rows: list[dict]) -> dict:
    """Return a capabilities dict from a list of cleaned row dicts.

    Each key in a cleaned row is a canonical column name (e.g. 'revenue',
    'order_date').  This is a pure function — no DB access.

    Parameters
    ----------
    cleaned_rows:
        List of dicts as produced by pipeline._clean_row (the ones that passed
        validation and will be inserted into sales_clean).

    Returns
    -------
    dict with bool fields ``revenue``, ``trend``, ``margin``, ``discount``,
    ``customer`` and a ``reasons`` dict for every False field.
    """
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
    """Same capability logic but takes pre-aggregated inputs.

    Parameters
    ----------
    canonical_populated:
        Set of canonical column names that have at least one non-null value.
    order_dates:
        List of ISO-format date strings from the order_date column (may be
        empty).

    Returns
    -------
    dict with bool fields ``revenue``, ``trend``, ``margin``, ``discount``,
    ``customer`` and a ``reasons`` dict for every False field.
    """
    # revenue
    has_revenue = "revenue" in canonical_populated

    # trend: order_date has at least 2 distinct years
    distinct_years: set[str] = set()
    for date_str in order_dates:
        try:
            year = str(date_str).split("-")[0]
            if year:
                distinct_years.add(year)
        except Exception:  # noqa: BLE001
            pass
    has_trend = len(distinct_years) >= 2

    # margin: cost or profit is populated
    has_margin = "cost" in canonical_populated or "profit" in canonical_populated

    # discount: discount_pct is populated
    has_discount = "discount_pct" in canonical_populated

    # customer: customer_id is populated
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
