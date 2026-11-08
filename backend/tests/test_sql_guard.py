import pytest
from agent.tools import guard_sql, SqlRejected


def test_guard_sql_allows_plain_queries():
    # Plain group by with single aggregate
    q1 = "SELECT region, round(sum(revenue), 2) AS rev FROM sales_clean WHERE region IN ('West', 'South') GROUP BY region"
    assert guard_sql(q1) == q1

    # Plain sum
    q2 = "SELECT sum(revenue) AS revenue FROM sales_clean"
    assert guard_sql(q2) == q2

    # Multiple single aggregates without arithmetic between them
    q3 = "SELECT count(*)::int AS orders, round(sum(revenue), 2) AS rev, round(avg(unit_price), 2) AS avg_price FROM sales_clean"
    assert guard_sql(q3) == q3

    # Group by with order by and limit
    q4 = "SELECT category, round(sum(revenue), 2) AS rev FROM sales_clean GROUP BY category ORDER BY rev DESC LIMIT 5"
    assert guard_sql(q4) == q4

    # Date extraction and grouping
    q5 = "SELECT extract(year FROM order_date)::int AS yr, round(sum(revenue), 2) AS rev FROM sales_clean GROUP BY 1 ORDER BY 1"
    assert guard_sql(q5) == q5

    # In-row arithmetic inside a single aggregate (row-level sum)
    q6 = "SELECT round(sum(revenue * quantity), 2) AS total FROM sales_clean"
    assert guard_sql(q6) == q6


def test_guard_sql_rejects_exact_45_21_query():
    exact_bad_query = (
        "SELECT round(max(total_revenue) - min(total_revenue),2) AS diff, "
        "round(((max(total_revenue) - min(total_revenue)) / max(total_revenue)) * 100, 2) AS pct "
        "FROM (SELECT region, round(sum(revenue),2) AS total_revenue "
        "FROM sales_clean WHERE region IN ('West','South') GROUP BY region) t"
    )
    with pytest.raises(SqlRejected) as exc_info:
        guard_sql(exact_bad_query)
    assert "run_python" in str(exc_info.value)


def test_guard_sql_rejects_aggregate_differences_and_ratios():
    # Aggregate difference
    with pytest.raises(SqlRejected) as exc_info:
        guard_sql("SELECT max(revenue) - min(revenue) FROM sales_clean")
    assert "run_python" in str(exc_info.value)

    # Aggregate ratio
    with pytest.raises(SqlRejected) as exc_info:
        guard_sql("SELECT sum(revenue) / count(*) FROM sales_clean")
    assert "run_python" in str(exc_info.value)

    # Percentage formula
    with pytest.raises(SqlRejected) as exc_info:
        guard_sql("SELECT (sum(revenue) - sum(cost)) / sum(revenue) * 100 FROM sales_clean")
    assert "run_python" in str(exc_info.value)

    # Outer query subtraction across aggregate subquery
    with pytest.raises(SqlRejected) as exc_info:
        guard_sql("SELECT t.rev1 - t.rev2 FROM (SELECT sum(revenue) as rev1, sum(cost) as rev2 FROM sales_clean) t")
    assert "run_python" in str(exc_info.value)


def test_guard_sql_rejects_security_violations():
    with pytest.raises(SqlRejected):
        guard_sql("INSERT INTO sales_clean (revenue) VALUES (10)")

    with pytest.raises(SqlRejected):
        guard_sql("SELECT sum(revenue) FROM sales_clean; DROP TABLE sales_clean")

    with pytest.raises(SqlRejected):
        guard_sql("SELECT * FROM public.sales_clean")

    with pytest.raises(SqlRejected):
        guard_sql("SELECT pg_read_file('secrets') FROM sales_clean")

