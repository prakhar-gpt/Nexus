"""The 25 Week 1 questions. Expected rows are filled in golden_set.json."""

QUESTIONS = [
    {
        "id": "q01",
        "kind": "sql",
        "question": "What is total revenue?",
        "sql": "SELECT round(sum(revenue), 2) AS total_revenue FROM sales_clean",
    },
    {
        "id": "q02",
        "kind": "sql",
        "question": "What is revenue by region?",
        "sql": (
            "SELECT region, round(sum(revenue), 2) AS revenue "
            "FROM sales_clean GROUP BY region ORDER BY revenue DESC, region"
        ),
    },
    {
        "id": "q03",
        "kind": "sql",
        "question": "What is revenue by category?",
        "sql": (
            "SELECT category, round(sum(revenue), 2) AS revenue "
            "FROM sales_clean GROUP BY category ORDER BY revenue DESC, category"
        ),
    },
    {
        "id": "q04",
        "kind": "sql",
        "question": "What is revenue by segment?",
        "sql": (
            "SELECT segment, round(sum(revenue), 2) AS revenue "
            "FROM sales_clean GROUP BY segment ORDER BY revenue DESC, segment"
        ),
    },
    {
        "id": "q05",
        "kind": "sql",
        "question": "How many sales lines are there?",
        "sql": "SELECT count(*) AS row_count FROM sales_clean",
    },
    {
        "id": "q06",
        "kind": "sql",
        "question": "How many distinct customers are there?",
        "sql": "SELECT count(DISTINCT customer_id) AS customers FROM sales_clean",
    },
    {
        "id": "q07",
        "kind": "sql",
        "question": "How many distinct products are there?",
        "sql": "SELECT count(DISTINCT product_id) AS products FROM sales_clean",
    },
    {
        "id": "q08",
        "kind": "sql",
        "question": "What is the first and last order date?",
        "sql": (
            "SELECT min(order_date)::text AS first_order, "
            "max(order_date)::text AS last_order FROM sales_clean"
        ),
    },
    {
        "id": "q09",
        "kind": "sql",
        "question": "What is revenue in 2017?",
        "sql": (
            "SELECT extract(year FROM order_date)::int AS year, "
            "round(sum(revenue), 2) AS revenue FROM sales_clean "
            "WHERE extract(year FROM order_date) = 2017 GROUP BY 1"
        ),
    },
    {
        "id": "q10",
        "kind": "sql",
        "question": "What is revenue in 2018?",
        "sql": (
            "SELECT extract(year FROM order_date)::int AS year, "
            "round(sum(revenue), 2) AS revenue FROM sales_clean "
            "WHERE extract(year FROM order_date) = 2018 GROUP BY 1"
        ),
    },
    {
        "id": "q11",
        "kind": "sql",
        "question": "Who are the top 5 customers by revenue?",
        "sql": (
            "SELECT customer_id, round(sum(revenue), 2) AS revenue "
            "FROM sales_clean GROUP BY customer_id "
            "ORDER BY revenue DESC, customer_id LIMIT 5"
        ),
    },
    {
        "id": "q12",
        "kind": "sql",
        "question": "What are the top 5 sub-categories by revenue?",
        "sql": (
            "SELECT sub_category, round(sum(revenue), 2) AS revenue "
            "FROM sales_clean GROUP BY sub_category "
            "ORDER BY revenue DESC, sub_category LIMIT 5"
        ),
    },
    {
        "id": "q13",
        "kind": "sql",
        "question": "What is Furniture revenue?",
        "sql": (
            "SELECT round(sum(revenue), 2) AS revenue FROM sales_clean "
            "WHERE category = 'Furniture'"
        ),
    },
    {
        "id": "q14",
        "kind": "sql",
        "question": "What percentage of revenue comes from the Consumer segment?",
        "sql": (
            "SELECT round(100 * sum(revenue) FILTER (WHERE segment = 'Consumer') "
            "/ sum(revenue), 2) AS consumer_pct FROM sales_clean"
        ),
    },
    {
        "id": "q15",
        "kind": "sql",
        "question": "What is revenue in the South?",
        "sql": (
            "SELECT round(sum(revenue), 2) AS revenue FROM sales_clean "
            "WHERE region = 'South'"
        ),
    },
    {
        "id": "q16",
        "kind": "sql",
        "question": "Which category has the highest revenue?",
        "sql": (
            "SELECT category, round(sum(revenue), 2) AS revenue FROM sales_clean "
            "GROUP BY category ORDER BY revenue DESC, category LIMIT 1"
        ),
    },
    {
        "id": "q17",
        "kind": "sql",
        "question": "What is revenue by year?",
        "sql": (
            "SELECT extract(year FROM order_date)::int AS year, "
            "round(sum(revenue), 2) AS revenue FROM sales_clean "
            "GROUP BY 1 ORDER BY 1"
        ),
    },
    {
        "id": "q18",
        "kind": "sql",
        "question": "What is Office Supplies revenue in the West?",
        "sql": (
            "SELECT round(sum(revenue), 2) AS revenue FROM sales_clean "
            "WHERE category = 'Office Supplies' AND region = 'West'"
        ),
    },
    {
        "id": "q19",
        "kind": "sql",
        "question": "How many sub-categories are there?",
        "sql": "SELECT count(DISTINCT sub_category) AS sub_categories FROM sales_clean",
    },
    {
        "id": "q20",
        "kind": "sql",
        "question": "What is the average revenue per line?",
        "sql": "SELECT round(avg(revenue), 2) AS avg_revenue FROM sales_clean",
    },
    {
        "id": "q21",
        "kind": "refusal",
        "question": "Which sub-categories lose money?",
        "missing": ["profit"],
    },
    {
        "id": "q22",
        "kind": "refusal",
        "question": "Are the losses linked to discounts?",
        "missing": ["discount_pct"],
    },
    {
        "id": "q23",
        "kind": "refusal",
        "question": "What is total quantity sold?",
        "missing": ["quantity"],
    },
    {
        "id": "q24",
        "kind": "refusal",
        "question": "What is average margin?",
        "missing": ["cost", "profit"],
    },
    {
        "id": "q25",
        "kind": "refusal",
        "question": "Which channel has the highest revenue?",
        "missing": ["channel"],
    },
]
