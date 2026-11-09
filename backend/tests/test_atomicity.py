"""Test ingest atomicity: concurrent query during ingest returns 0 rows, not a partial count."""

import io
import json
import threading
import time
import pytest

from ingest.store import get_writer_connection, execute, sql_id
from agent.nexus.tools import run_sql


def test_ingest_atomicity_concurrent_reader():
    # 1. Create a clean test workspace
    ws = execute("INSERT INTO workspaces (name) VALUES ('Atomicity Test') RETURNING id")
    ws_id = str(ws[0]["id"])

    up = execute(
        f"INSERT INTO uploads (workspace_id, original_name, stored_name, sha256, size, status) "
        f"VALUES ({sql_id(ws_id)}, 'test.csv', 'test.csv', 'dummy', 100, 'processing') RETURNING id"
    )
    up_id = str(up[0]["id"])

    # Prepare 5,000 synthetic rows in a TSV buffer
    buf = io.StringIO()
    for i in range(5000):
        attrs = json.dumps({"note": f"row_{i}"})
        line = f"{ws_id}\t{up_id}\t2024-01-01\tcust_{i}\tprod_{i}\t1\t100.00\t100.00\t0.00\t50.00\t50.00\tConsumer\tWest\tTech\tPhones\tOnline\t{attrs}\n"
        buf.write(line)
    buf.seek(0)

    reader_observed_counts = []
    ingest_started = threading.Event()
    ingest_in_progress = threading.Event()
    can_commit = threading.Event()

    def ingest_worker():
        conn = get_writer_connection()
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TEMP TABLE staging_sales AS SELECT * FROM sales_clean WITH NO DATA;
                    ALTER TABLE staging_sales DROP COLUMN id;
                """)
                cur.copy_expert("""
                    COPY staging_sales (
                        workspace_id, upload_id, order_date, customer_id, product_id,
                        quantity, revenue, unit_price, discount_pct, cost, profit,
                        segment, region, category, sub_category, channel, attributes
                    ) FROM STDIN WITH (FORMAT text, NULL '\\N')
                """, buf)
                cur.execute("""
                    INSERT INTO sales_clean (
                        workspace_id, upload_id, order_date, customer_id, product_id,
                        quantity, revenue, unit_price, discount_pct, cost, profit,
                        segment, region, category, sub_category, channel, attributes
                    ) SELECT
                        workspace_id, upload_id, order_date, customer_id, product_id,
                        quantity, revenue, unit_price, discount_pct, cost, profit,
                        segment, region, category, sub_category, channel, attributes
                    FROM staging_sales;
                """)
                ingest_started.set()
                # Wait while concurrent reader probes
                can_commit.wait(timeout=5)
                cur.execute(f"UPDATE uploads SET status = 'loaded' WHERE id = {up_id}")
        conn.close()

    def reader_worker():
        ingest_started.wait(timeout=5)
        # Probe database while writer has rows inserted but uncommitted
        for _ in range(5):
            res = run_sql("SELECT count(*) AS cnt FROM sales_clean", ws_id)
            cnt = int(res[0]["cnt"]) if res else 0
            reader_observed_counts.append(cnt)
            time.sleep(0.02)
        can_commit.set()

    t_ingest = threading.Thread(target=ingest_worker)
    t_reader = threading.Thread(target=reader_worker)

    t_ingest.start()
    t_reader.start()

    t_ingest.join()
    t_reader.join()

    # During uncommitted ingestion, reader MUST observe 0 rows, NEVER a partial count
    assert len(reader_observed_counts) > 0
    assert all(c == 0 for c in reader_observed_counts), f"Reader saw partial count: {reader_observed_counts}"

    # After commit, reader observes all 5,000 rows
    post_commit_res = run_sql("SELECT count(*) AS cnt FROM sales_clean", ws_id)
    assert int(post_commit_res[0]["cnt"]) == 5000

