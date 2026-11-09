"""Unit and adversarial tests for Stage 1 source provenance, evidence tagging, and binding."""

from __future__ import annotations

from decimal import Decimal
from agent.nexus.checker import check_answer
from agent.nexus.provenance import (
    ClaimProvenance,
    EvidenceRecord,
    bind_claim,
    check_truncation_caveat,
    derive_column_kind,
    is_currency_or_percent_claim,
    synthesize_evidence_from_rows,
)


def test_derive_column_kind():
    """Derive appropriate kind based on name, catalog role, and count flags."""
    assert derive_column_kind("order_id", catalog_role="identifier") == "identifier"
    assert derive_column_kind("postal_code") == "identifier"
    assert derive_column_kind("sales", catalog_role="measure") == "measure"
    assert derive_column_kind("total_rows") == "count"
    assert derive_column_kind("any_col", is_count_aggregate=True) == "count"
    assert derive_column_kind("order_date") == "date"


def test_currency_or_percent_cannot_match_identifier():
    """A currency claim like $90,210 cannot match an identifier like zip code 90210."""
    ev = [
        EvidenceRecord(
            query_id=1,
            dataset_id="ds-1",
            table_label="customers",
            column="zip_code",
            kind="identifier",
            row_index=0,
            value=Decimal("90210"),
            raw_string="90210",
        )
    ]
    r = check_answer("Customer lives in zip code $90,210.", [], evidence_records=ev)
    assert not r["verified"]
    assert r["status"] == "caveat"
    assert any("90,210" in u for u in r["untraced"])


def test_currency_or_percent_cannot_match_count():
    """A percentage claim like 4% cannot match a count or row_count of 4."""
    ev = [
        EvidenceRecord(
            query_id=1,
            dataset_id="ds-1",
            table_label="orders",
            column="row_count",
            kind="count",
            row_index=0,
            value=Decimal("4"),
            raw_string="4",
        )
    ]
    r = check_answer("Market share expanded by 4%.", [], evidence_records=ev)
    assert not r["verified"]
    assert r["status"] == "caveat"
    assert any("4%" in u for u in r["untraced"])


def test_named_dataset_mismatch_caveat():
    """Matching a number from an unmentioned dataset when another dataset was named triggers caveat."""
    ev = [
        EvidenceRecord(
            query_id=1,
            dataset_id="ds-returns",
            table_label="returns",
            column="refund",
            kind="measure",
            row_index=0,
            value=Decimal("500"),
            raw_string="500",
        )
    ]
    # Answer explicitly claims this comes from Superstore, but evidence is only in returns
    r = check_answer(
        "According to Superstore data, total sales were $500.",
        [],
        evidence_records=ev,
    )
    assert not r["verified"]
    assert r["status"] == "caveat"
    assert any("found in a different dataset" in u for u in r["untraced"])


def test_truncation_caveat_on_total():
    """Asserting a total over a truncated query triggers partial-result caveat."""
    queries = [
        {
            "query_id": 1,
            "sql": "SELECT * FROM transactions",
            "truncated": True,
            "row_count": 200,
        }
    ]
    ev = [
        EvidenceRecord(
            query_id=1,
            dataset_id="ds-tx",
            table_label="transactions",
            column="amount",
            kind="measure",
            row_index=0,
            value=Decimal("50000"),
            raw_string="50000",
        )
    ]
    r = check_answer(
        "Total overall transactions amounted to $50,000.",
        [],
        evidence_records=ev,
        queries=queries,
    )
    assert not r["verified"]
    assert r["status"] == "caveat"
    assert any("partial result" in u for u in r["untraced"])


def test_provenance_also_in_and_shape():
    """Verify provenance captures primary query, secondary queries in also_in, and fields."""
    ev = [
        EvidenceRecord(
            query_id=1,
            dataset_id="ds-1",
            table_label="east_sales",
            column="revenue",
            kind="measure",
            row_index=2,
            value=Decimal("1200"),
            raw_string="1200",
        ),
        EvidenceRecord(
            query_id=2,
            dataset_id="ds-2",
            table_label="west_sales",
            column="revenue",
            kind="measure",
            row_index=5,
            value=Decimal("1200"),
            raw_string="1200",
        ),
    ]
    r = check_answer("Revenue was $1,200.", [], evidence_records=ev)
    assert r["verified"]
    assert len(r["provenance"]) >= 1
    p = r["provenance"][0]
    assert p["query_id"] == 1
    assert p["dataset_id"] == "ds-1"
    assert p["column"] == "revenue"
    assert p["row_index"] == 2
    assert 2 in p["also_in"]


def test_backward_compatibility_synthesis():
    """When evidence_records is omitted, synthesize_evidence_from_rows preserves verification."""
    rows = [{"sales": "850.50", "region": "North"}]
    r = check_answer("North region recorded sales of $850.50.", rows)
    assert r["verified"]
    assert len(r["provenance"]) >= 1
    p = r["provenance"][0]
    assert p["column"] == "sales"
    assert p["source"] == "data"

