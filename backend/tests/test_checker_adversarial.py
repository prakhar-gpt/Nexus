"""Adversarial and boundary test cases for the deterministic claim-to-evidence checker."""

from __future__ import annotations

from decimal import Decimal
from agent.nexus.checker import check_answer
from agent.nexus.extraction import extract_numbers, is_contextual_year, normalize_raw_number
from agent.nexus.normalization import normalize_text, strip_fenced_code_blocks


# ---------------------------------------------------------------------------
# Phase A Tests: Cheap Holes & Formatting
# ---------------------------------------------------------------------------

def test_code_spans_fenced_vs_inline():
    """Fenced code blocks are stripped, but inline code spans are preserved as claims."""
    # Fenced SQL block containing LIMIT 10 should NOT extract '10' as a claim
    text_fenced = (
        "Here is the query executed:\n"
        "```sql\n"
        "SELECT * FROM sales_clean LIMIT 10\n"
        "```\n"
        "Total sales were $500."
    )
    r_fenced = check_answer(text_fenced, [{"sales": "500"}])
    assert r_fenced["verified"]
    assert "500" in r_fenced["matched"] or "$500" in r_fenced["matched"]

    # Inline code span with fake metric MUST be treated as a claim and caught
    text_inline = "Total revenue reached `$9,999,999.00` according to records."
    r_inline = check_answer(text_inline, [{"revenue": "1000000.00"}])
    assert not r_inline["verified"]
    assert r_inline["status"] == "caveat"
    assert any("9,999,999.00" in u for u in r_inline["untraced"])


def test_contextual_years():
    """1900-2099 is exempt only when context marks it as a date/year."""
    # Preceded by 'In' -> exempt
    r_in = check_answer("In 2018, sales were 450.", [{"sales": "450"}])
    assert r_in["verified"]

    # Preceded by 'during' or 'FY' -> exempt
    r_fy = check_answer("During FY 2024, volume was 500.", [{"vol": "500"}])
    assert r_fy["verified"]

    # Bare integer without year marker is a claim and triggers caveat if not in data
    r_bare = check_answer("Total unit sales were 2024 across all regions.", [{"unit_count": "58000"}])
    assert not r_bare["verified"]
    assert r_bare["status"] == "caveat"
    assert "2024" in r_bare["untraced"]


def test_exact_token_date_matching():
    """Only digits belonging to the date token are exempt; neighboring numbers are claims."""
    # Clean date with unicode hyphen should be verified
    r_date = check_answer("Order on 2018‑12‑30 had sales of 100.", [{"sales": "100"}])
    assert r_date["verified"]

    # Number adjacent to date is NOT exempted by sliding window
    r_leak = check_answer("2022-01-01: 888888 in gross sales.", [{"sales": "150.00"}])
    assert not r_leak["verified"]
    assert "888888" in r_leak["untraced"]


def test_unicode_punctuation_normalization():
    """Non-breaking hyphens, en-dashes, minus signs, and non-breaking spaces are normalized."""
    raw = "Sales on 2016‑01‑12 were 282.32 dollars."
    norm = normalize_text(raw)
    assert "2016-01-12" in norm
    assert "282.32 dollars" in norm

    r = check_answer(raw, [{"total_sales": "282.32"}])
    assert r["verified"]
    assert "01" not in r["untraced"]
    assert "12" not in r["untraced"]


def test_top_n_plausibility():
    """Top N is exempt only when N is plausible for row count or SQL limit."""
    # Plausible: Top 5 with 10 rows
    rows_10 = [{"sales": str(i * 100)} for i in range(1, 11)]
    r_plausible = check_answer("The Top 5 stores had sales of 500.", rows_10)
    assert r_plausible["verified"]

    # Implausible: Top 5000000 with 10 rows returned
    r_implausible = check_answer("The Top 5000000 orders generated most sales of 500.", rows_10)
    assert not r_implausible["verified"]
    assert any("5000000" in u for u in r_implausible["untraced"])


# ---------------------------------------------------------------------------
# Phase B Tests: Verdict Policy & Arithmetic
# ---------------------------------------------------------------------------

def test_zero_tool_answers():
    """Zero-tool answers that are not refusals, clarifications, or greetings are caveats."""
    # Pure narrative qualitative claim with 0 numbers
    r_narrative = check_answer(
        "Technology was the standout top performer, outstripping all other departments.",
        [],
    )
    assert not r_narrative["verified"]
    assert r_narrative["status"] == "caveat"
    assert "Not checked against your data" in r_narrative["untraced"]

    # Conversational greeting passes without caveat
    r_greet = check_answer("Hello! How can I help you analyze the data today?", [])
    assert r_greet["verified"]
    assert r_greet["status"] == "verified"


def test_prompt_stated_numbers():
    """Prompt-stated numbers are untraced unless they are an echoed year or Top N."""
    # User stated revenue figure echoed in answer
    q = "Why did our profit plummet to $42,000 last quarter?"
    a = "Profit dropped to $42,000 due to supply chain disruptions."
    r = check_answer(a, [], question_text=q)
    assert not r["verified"]
    assert r["status"] == "caveat"
    assert any("stated in your message" in u for u in r["untraced"])

    # Echoed year from prompt remains exempt
    q_year = "What happened in 2017?"
    a_year = "In 2017, sales were 500."
    r_year = check_answer(a_year, [{"sales": "500"}], question_text=q_year)
    assert r_year["verified"]


def test_refusals_and_clarifications():
    """Refusals have status 'refused' (verified=False); untraced numbers force caveat."""
    # Standard clean refusal
    r_clean = check_answer(
        "Cannot answer. profit has no values in this workspace, so the question is refused.",
        [],
        kind="refusal",
    )
    assert r_clean["status"] == "refused"
    assert not r_clean["verified"]
    assert len(r_clean["untraced"]) == 0

    # Refusal containing hallucinated statistics forces caveat
    r_halluc = check_answer(
        "Cannot answer. Although our churn rate is 18.5%, this dataset lacks churn metrics.",
        [],
        kind="refusal",
    )
    assert r_halluc["status"] == "caveat"
    assert not r_halluc["verified"]
    assert any("18.5%" in u for u in r_halluc["untraced"])

    # Clarification asking user for guidance
    r_clarif = check_answer("Did you want to see sales by state or by category?", [], kind="clarification")
    assert r_clarif["status"] == "verified"
    assert r_clarif["verified"]


def test_sign_handling_loss_context():
    """Negative source value matches positive claim when loss context is present."""
    # Negative profit in SQL, described as 'net loss of $12,500'
    rows = [{"profit": "-12500.00"}]
    r_loss = check_answer("Central recorded a net loss of $12,500.00.", rows)
    assert r_loss["verified"]

    # Without loss word, sign mismatch is flagged as caveat
    r_pos = check_answer("Central recorded a profit of $12,500.00.", rows)
    assert not r_pos["verified"]
    assert any("12,500.00" in u for u in r_pos["untraced"])


def test_integer_rounding():
    """Accept floor or round of source values for integer claims."""
    rows = [{"revenue": "2261536.78"}]
    # Floor: 2,261,536
    r_floor = check_answer("Total revenue was $2,261,536.", rows)
    assert r_floor["verified"]

    # Round: 2,261,537
    r_round = check_answer("Total revenue was $2,261,537.", rows)
    assert r_round["verified"]

    # Grossly inaccurate integer should fail
    r_bad = check_answer("Total revenue was $2,261,540.", rows)
    assert not r_bad["verified"]


def test_tolerance_scaled_billions():
    """Adv_12: $1.2B matches 1,195,000,000 (within 5% of step); off-step value fails."""
    # 1,195,000,000 vs $1.2B: step is 100M, tolerance is 5M -> 1,195,000,000 is exactly on boundary
    rows_boundary = [{"val": "1195000000"}]
    r_pass = check_answer("The enterprise valuation stood at $1.2B.", rows_boundary)
    assert r_pass["verified"]

    # Value off by more than half a rounding step (e.g. 1,140,000,000) must fail
    rows_off = [{"val": "1140000000"}]
    r_fail = check_answer("The enterprise valuation stood at $1.2B.", rows_off)
    assert not r_fail["verified"]
    assert r_fail["status"] == "caveat"


def test_percent_vs_fraction_distinction():
    """Adv_20: Verify that 15.4 in data does not match 154% in answer."""
    rows = [{"rate": "15.4"}]
    r = check_answer("The return rate was 154%.", rows)
    assert not r["verified"]
    assert any("154%" in u for u in r["untraced"])


def test_checker_result_shape_and_latency():
    """Ensure checker_result includes status, verified, provenance, and elapsed ms."""
    rows = [{"sales": "450"}]
    r = check_answer("Sales were $450 in 2018.", rows)
    assert "status" in r
    assert "verified" in r
    assert "untraced" in r
    assert "matched" in r
    assert "provenance" in r
    assert "ms" in r
    assert r["ms"] >= 0.0

