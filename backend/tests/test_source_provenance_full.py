"""Comprehensive test suite for source provenance, Python input lineage, and row rewriting."""

from __future__ import annotations

import uuid
from decimal import Decimal
import pytest
from fastapi import HTTPException

from agent.nexus.checker import (
    ClaimProvenance,
    EvidenceRecord,
    bind_claim,
    check_answer,
    check_truncation_caveat,
    collect_python_evidence,
    collect_sql_evidence,
    extract_python_input_lineage,
)
from agent.nexus.tools.run_sql import guard_sql
from api.services.provenance_service import (
    get_source_record,
    is_sql_rewritable_for_rows,
    rewrite_sql_for_rows,
)
from db.models import Run


# ---------------------------------------------------------------------------
# 1. Call-record Persistence and Size Bounds
# ---------------------------------------------------------------------------

def test_sql_call_record_size_bounds():
    """Preview rows are capped at 25 and cell values are capped to 200 characters."""
    found = [{"col1": "A" * 300, "col2": i} for i in range(100)]
    q_info, ev_recs = collect_sql_evidence("ws-1", 1, "SELECT col1, col2 FROM t", found)

    assert q_info["query_id"] == 1
    assert q_info["tool"] == "sql"
    assert len(q_info["preview_rows"]) == 25
    assert len(q_info["preview_rows"][0]["col1"]) == 200
    assert q_info["row_count"] == 100


def test_python_call_record_size_bounds():
    """Python code is capped at 4000 characters and inputs capped at 50."""
    long_code = "# " + ("x" * 5000)
    many_inputs = list(range(100))
    py_results = {"growth": 15.5}

    q_info, ev_recs = collect_python_evidence(2, long_code, many_inputs, py_results)

    assert q_info["tool"] == "python"
    assert len(q_info["code"]) <= 4000
    assert len(q_info["inputs"]) <= 50
    assert ev_recs[0].kind == "python"


# ---------------------------------------------------------------------------
# 2. Python Input Lineage
# ---------------------------------------------------------------------------

def test_python_lineage_exact_and_tolerance_match():
    """Values in Python code match prior SQL evidence exactly or within tolerance."""
    sql_ev = [
        EvidenceRecord(
            query_id=1,
            dataset_id="ds-1",
            table_label="Superstore",
            column="sales",
            kind="measure",
            row_index=0,
            value=Decimal("450000"),
            raw_string="450000",
        ),
        EvidenceRecord(
            query_id=2,
            dataset_id="ds-1",
            table_label="Superstore",
            column="sales",
            kind="measure",
            row_index=0,
            value=Decimal("320000"),
            raw_string="320000",
        ),
    ]

    code = """
west = 450000
south = 320000
diff = west - south
result = {'diff': diff}
"""
    inputs, derived_from = extract_python_input_lineage(code, [], prior_evidence=sql_ev)

    assert len(inputs) >= 2
    west_inp = next(i for i in inputs if i["name"] == "west")
    south_inp = next(i for i in inputs if i["name"] == "south")

    assert west_inp["query_id"] == 1
    assert west_inp["column"] == "sales"
    assert not west_inp["literal_in_code"]

    assert south_inp["query_id"] == 2
    assert south_inp["column"] == "sales"
    assert not south_inp["literal_in_code"]

    assert derived_from == [1, 2]


def test_python_lineage_ambiguous_value_with_also_in():
    """When a value appears in multiple SQL queries, the earliest is primary and others are also_in."""
    sql_ev = [
        EvidenceRecord(
            query_id=1,
            dataset_id="ds-1",
            table_label="east_region",
            column="profit",
            kind="measure",
            row_index=0,
            value=Decimal("5000"),
            raw_string="5000",
        ),
        EvidenceRecord(
            query_id=3,
            dataset_id="ds-2",
            table_label="west_region",
            column="profit",
            kind="measure",
            row_index=0,
            value=Decimal("5000"),
            raw_string="5000",
        ),
    ]

    code = "target = 5000; result = {'met': target >= 5000}"
    inputs, derived = extract_python_input_lineage(code, [], prior_evidence=sql_ev)

    target_inp = next(i for i in inputs if i["name"] == "target")
    assert target_inp["query_id"] == 1
    assert target_inp["also_in"] == [3]
    assert not target_inp["literal_in_code"]
    assert 1 in derived


def test_python_lineage_literal_in_code():
    """A constant in code not found in any SQL result is visibly listed as literal in code."""
    sql_ev = [
        EvidenceRecord(
            query_id=1,
            dataset_id="ds-1",
            table_label="Superstore",
            column="sales",
            kind="measure",
            row_index=0,
            value=Decimal("100"),
            raw_string="100",
        )
    ]

    code = "growth_pct = 15.5; result = {'pct': growth_pct}"
    inputs, derived = extract_python_input_lineage(code, [], prior_evidence=sql_ev)

    pct_inp = next(i for i in inputs if i["name"] == "growth_pct")
    assert pct_inp["query_id"] is None
    assert pct_inp["literal_in_code"] is True


def test_python_output_inherits_derived_from():
    """Python calculation evidence records inherit derived_from from their matched inputs."""
    sql_ev = [
        EvidenceRecord(
            query_id=1,
            dataset_id="ds-1",
            table_label="Superstore",
            column="sales",
            kind="measure",
            row_index=0,
            value=Decimal("200"),
            raw_string="200",
        )
    ]
    code = "val = 200; result = {'doubled': val * 2}"
    q_info, ev_recs = collect_python_evidence(2, code, [], {"doubled": 400}, prior_evidence=sql_ev)

    assert q_info["derived_from"] == [1]
    assert len(ev_recs) == 1
    assert ev_recs[0].derived_from == [1]
    assert ev_recs[0].kind == "python"


# ---------------------------------------------------------------------------
# 3. Claim Binding Rules
# ---------------------------------------------------------------------------

def test_claim_binding_currency_cannot_match_identifier_or_count():
    """Currency claims cannot bind to identifier or count evidence records."""
    ev = [
        EvidenceRecord(
            query_id=1,
            dataset_id="ds-1",
            table_label="orders",
            column="order_id",
            kind="identifier",
            row_index=0,
            value=Decimal("500"),
            raw_string="500",
        ),
        EvidenceRecord(
            query_id=1,
            dataset_id="ds-1",
            table_label="orders",
            column="row_count",
            kind="count",
            row_index=0,
            value=Decimal("500"),
            raw_string="500",
        ),
    ]

    best, also_in, mismatch = bind_claim(Decimal("500"), "$500", ev, "$500 total", 0)
    assert best is None


def test_claim_binding_mismatch_dataset_caveat():
    """Matching a different dataset than the one named in the text produces caveat."""
    ev = [
        EvidenceRecord(
            query_id=1,
            dataset_id="ds-returns",
            table_label="returns",
            column="amount",
            kind="measure",
            row_index=0,
            value=Decimal("150"),
            raw_string="150",
        )
    ]
    res = check_answer("In the Superstore dataset, total was $150.", [], evidence_records=ev)
    assert not res["verified"]
    assert any("found in a different dataset" in u for u in res["untraced"])


def test_claim_binding_python_claim_carries_derived_from():
    """When a claim matches a Python result, the claim provenance record preserves derived_from."""
    py_ev = [
        EvidenceRecord(
            query_id=2,
            dataset_id=None,
            table_label="Calculated by Python",
            column="gap",
            kind="python",
            row_index=0,
            value=Decimal("1250.50"),
            raw_string="1250.50",
            derived_from=[1, 3],
        )
    ]
    res = check_answer("The revenue gap is $1,250.50.", [], evidence_records=py_ev)
    assert res["verified"]
    claim_prov = res["provenance"][0]
    assert claim_prov["source"] == "python"
    assert claim_prov["query_id"] == 2
    assert claim_prov["derived_from"] == [1, 3]


# ---------------------------------------------------------------------------
# 4. Source Endpoint & Authorization
# ---------------------------------------------------------------------------

def test_get_source_record_reads_stored_data_only():
    """Source record is returned strictly from stored checker_result without executing queries."""
    run = Run(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        question="What was revenue?",
        checker_result={
            "queries": [
                {
                    "query_id": 1,
                    "tool": "sql",
                    "sql": "SELECT sum(sales) FROM superstore",
                    "dataset_id": "ds-1",
                    "table_label": "Superstore",
                    "columns": ["sum"],
                    "row_count": 1,
                    "preview_rows": [{"sum": "450000"}],
                }
            ],
            "provenance": [
                {
                    "claim": "$450,000",
                    "status": "matched",
                    "source": "data",
                    "query_id": 1,
                    "row_index": 0,
                }
            ],
        },
    )

    rec = get_source_record(run, 1, claim_index=0)
    assert rec["origin_type"] == "data"
    assert rec["origin_label"] == "From your data"
    assert rec["sql"] == "SELECT sum(sales) FROM superstore"
    assert rec["matched_row"] == {"sum": "450000"}


def test_get_source_record_not_found():
    """Querying an unknown query_id raises 404."""
    run = Run(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        question="test",
        checker_result={"queries": []},
    )
    with pytest.raises(HTTPException) as exc_info:
        get_source_record(run, 99)
    assert exc_info.value.status_code == 404


def test_get_source_record_removed_dataset_state():
    """A deleted dataset flags dataset_removed=True without crashing or leaking rows."""
    missing_ds_id = str(uuid.uuid4())
    run = Run(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        question="test",
        checker_result={
            "queries": [
                {
                    "query_id": 1,
                    "tool": "sql",
                    "sql": "SELECT sales FROM old_table",
                    "dataset_id": missing_ds_id,
                    "table_label": "Old Table",
                    "preview_rows": [{"sales": "100"}],
                }
            ]
        },
    )
    rec = get_source_record(run, 1)
    assert rec["dataset_status"] == "removed"
    assert rec["dataset_removed"] is True
    assert rec["rows"] == [{"sales": "100"}]


# ---------------------------------------------------------------------------
# 5. Stage 4: "View the rows behind this" AST Rewriter
# ---------------------------------------------------------------------------

def test_ast_rewrite_whitelisted_aggregate(monkeypatch):
    """Simple aggregate query rewrites to raw rows and passes SQL guard."""
    import sys
    run_sql_module = sys.modules.get("agent.nexus.tools.run_sql")
    monkeypatch.setattr(run_sql_module, "get_allowed_tables", lambda *args, **kwargs: {"superstore"})
    sql = "SELECT category, sum(sales) as total FROM superstore WHERE sales > 100 GROUP BY category"
    allowed, reason = is_sql_rewritable_for_rows(sql)
    assert allowed
    assert reason is None

    rewritten, _ = rewrite_sql_for_rows(sql)
    assert "SELECT * FROM superstore" in rewritten
    assert "WHERE sales > 100" in rewritten
    assert "GROUP BY" not in rewritten
    assert "sum" not in rewritten

    # Ensure rewritten SQL passes guard_sql
    guarded = guard_sql(rewritten, workspace_id=None)
    assert "superstore" in guarded


@pytest.mark.parametrize(
    "bad_sql",
    [
        "WITH cte AS (SELECT * FROM t) SELECT sum(x) FROM cte",      # CTE
        "SELECT a.x, sum(b.y) FROM a JOIN b ON a.id = b.id GROUP BY a.x", # Join
        "SELECT sum(x) FROM (SELECT x FROM t) subq",                 # Subquery
        "SELECT x, sum(y) OVER (PARTITION BY x) FROM t",             # Window function
        "SELECT category, sum(sales) FROM t GROUP BY category HAVING sum(sales) > 1000", # HAVING
        "SELECT sum(DISTINCT sales) FROM t",                         # DISTINCT aggregate
        "SELECT sum(x) FROM a UNION SELECT sum(x) FROM b",           # Set op
    ],
)
def test_ast_rewrite_rejects_unwhitelisted_shapes(bad_sql):
    """AST rewrite safely rejects non-whitelisted SQL queries with not_rewritable."""
    allowed, reason = is_sql_rewritable_for_rows(bad_sql)
    assert not allowed
    assert reason is not None


def test_export_csv_is_the_uploaded_slice(monkeypatch):
    """The download is the file's own columns, without our bookkeeping."""
    from api.services.provenance_service import export_rows_behind_query_csv, get_rows_behind_query

    stored = {
        "row_id": 318,
        "workspace_id": "137a6bee-aa0f-4b93-82b3-2b079fa69201",
        "upload_id": "6a1f12d2-184b-4f91-9976-3a0dbb4e16b6",
        "source_row": 319,
        "src_row_id": 318,
        "sub_category": "Chairs",
        "sales": "135.8820",
    }

    def fake_execute(sql, workspace_id=None):
        if "count(*)" in sql.lower():
            return [{"total_rows": 1}]
        return [dict(stored)]

    monkeypatch.setattr("api.services.provenance_service.guard_sql", lambda sql, workspace_id=None: sql)
    monkeypatch.setattr("api.services.provenance_service.execute_sql", fake_execute)
    run = Run(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        question="chairs in new york",
        checker_result={
            "queries": [{
                "query_id": 1,
                "tool": "sql",
                "sql": "SELECT sub_category, sum(sales) AS val FROM superstore GROUP BY sub_category",
            }]
        },
    )

    response = export_rows_behind_query_csv(run, 1)
    text = response.body.decode()
    header, row = text.splitlines()
    assert header.split(",") == ["src_row_id", "sub_category", "sales"]
    assert row.split(",") == ["318", "Chairs", "135.8820"]
    assert "workspace_id" not in header
    assert "upload_id" not in header

    preview = get_rows_behind_query(run, 1)
    assert list(preview["rows"][0]) == ["src_row_id", "sub_category", "sales"]


def test_get_source_record_python_upstream_queries():
    """Python record enriches upstream_queries for full lineage mapping."""
    run = Run(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        question="test",
        checker_result={
            "queries": [
                {
                    "query_id": 1,
                    "tool": "sql",
                    "sql": "SELECT sub_category, sum(sales) AS val FROM superstore GROUP BY sub_category",
                    "dataset_id": "ds-1",
                    "table_label": "Superstore",
                    "columns": ["sub_category", "val"],
                    "preview_rows": [{"sub_category": "Phones", "val": 327782.45}],
                    "row_count": 17,
                },
                {
                    "query_id": 2,
                    "tool": "python",
                    "code": "pct_gap = 10818.95",
                    "inputs": [
                        {
                            "name": "best_val",
                            "value": 327782.45,
                            "raw": "327782.45",
                            "query_id": 1,
                            "row_index": 0,
                            "entity": "Phones",
                        }
                    ],
                    "derived_from": [1],
                    "result": {"pct_gap": 10818.95},
                },
            ]
        },
    )

    rec = get_source_record(run, 2)
    assert rec["origin_type"] == "python"
    assert "upstream_queries" in rec
    assert len(rec["upstream_queries"]) == 1
    assert rec["upstream_queries"][0]["query_id"] == "1"
    assert rec["upstream_queries"][0]["dataset_label"] == "Superstore"
    assert rec["inputs"][0]["row_index"] == 0
    assert rec["inputs"][0]["entity"] == "Phones"


