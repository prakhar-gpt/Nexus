"""Tests for first-class threads, workspace isolation, and per-chat dataset selection."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app
from agent.nexus.tools.run_sql import SqlRejected, guard_sql
from agent.nexus.tools.get_schema import execute_schema
from api.services.workspace_service import (
    create_workspace,
    get_or_create_thread,
    get_turns,
    list_threads,
    list_workspace_datasets,
    remove_dataset,
    update_thread_datasets,
)
from ingest.store import execute, sql_id


@pytest.fixture
def test_workspaces():
    ws1 = create_workspace("Test WS 1")
    ws2 = create_workspace("Test WS 2")
    ws1_id = ws1["id"]
    ws2_id = ws2["id"]
    yield ws1_id, ws2_id

    # Cleanup in proper dependency order
    execute(f"DELETE FROM datasets WHERE workspace_id IN ({sql_id(ws1_id)}, {sql_id(ws2_id)})")
    execute(f"DELETE FROM uploads WHERE workspace_id IN ({sql_id(ws1_id)}, {sql_id(ws2_id)})")
    execute(f"DELETE FROM threads WHERE workspace_id IN ({sql_id(ws1_id)}, {sql_id(ws2_id)})")
    execute(f"DELETE FROM runs WHERE workspace_id IN ({sql_id(ws1_id)}, {sql_id(ws2_id)})")
    execute(f"DELETE FROM workspaces WHERE id IN ({sql_id(ws1_id)}, {sql_id(ws2_id)})")


def make_test_upload(workspace_id: int | str, name: str = "test.csv") -> str:
    row = execute(
        f"INSERT INTO uploads (workspace_id, original_name, stored_name, sha256, size, status) "
        f"VALUES ({sql_id(workspace_id)}, '{name}', '{name}', 'sha_{name}', 100, 'loaded') RETURNING id"
    )
    return str(row[0]["id"])


def test_thread_creation_and_workspace_isolation(test_workspaces):
    ws1_id, ws2_id = test_workspaces
    client = TestClient(app)

    # 1. Create a dummy upload & dataset in ws1
    up_id = make_test_upload(ws1_id, "test_1.csv")
    ds = execute(
        f"INSERT INTO datasets (workspace_id, upload_id, table_name, table_label, grain) "
        f"VALUES ({sql_id(ws1_id)}, {sql_id(up_id)}, 'ds_test_1', 'Test Dataset', 'One row per test') RETURNING id"
    )
    ds_id = str(ds[0]["id"])

    # 2. Get or create thread in ws1 -> auto-populates with ds_id
    t1 = get_or_create_thread(ws1_id, "chat-1")
    assert t1["id"] == "chat-1"
    assert t1["workspace_id"] == ws1_id
    assert ds_id in t1["selected_dataset_ids"]

    # 3. Verify ws2 cannot access or list ws1's thread
    ws2_threads = list_threads(ws2_id)
    assert not any(t["id"] == "chat-1" for t in ws2_threads)

    # 4. Attempting to update ws1's thread through ws2 fails or isolates cleanly
    res = client.patch(
        f"/workspaces/{ws2_id}/threads/chat-1/datasets",
        json={"dataset_ids": [ds_id]},
    )
    assert res.status_code == 200
    # ws2 thread was created for ws2, but ds_id does NOT belong to ws2 so selected_dataset_ids must be empty!
    assert res.json()["selected_dataset_ids"] == []

    # 5. Clean up dataset
    execute(f"DELETE FROM datasets WHERE id = {sql_id(ds_id)}")


def test_sql_guard_per_chat_dataset_enforcement(test_workspaces):
    ws1_id, _ = test_workspaces

    # Create two uploads and datasets in ws1
    up1 = make_test_upload(ws1_id, "active.csv")
    up2 = make_test_upload(ws1_id, "disabled.csv")
    ds1 = execute(
        f"INSERT INTO datasets (workspace_id, upload_id, table_name, table_label, grain) "
        f"VALUES ({sql_id(ws1_id)}, {sql_id(up1)}, 'ds_active', 'Active Data', 'One row per test') RETURNING id"
    )
    ds2 = execute(
        f"INSERT INTO datasets (workspace_id, upload_id, table_name, table_label, grain) "
        f"VALUES ({sql_id(ws1_id)}, {sql_id(up2)}, 'ds_disabled', 'Disabled Data', 'One row per test') RETURNING id"
    )
    id1 = ds1[0]["id"]
    id2 = ds2[0]["id"]

    # When both are allowed
    assert guard_sql("SELECT count(*) FROM ds_active", workspace_id=ws1_id, allowed_dataset_ids=[id1, id2])
    assert guard_sql("SELECT count(*) FROM ds_disabled", workspace_id=ws1_id, allowed_dataset_ids=[id1, id2])

    # When only ds1 is allowed
    assert guard_sql("SELECT count(*) FROM ds_active", workspace_id=ws1_id, allowed_dataset_ids=[id1])

    # Querying ds_disabled when not in allowed list raises specific message
    with pytest.raises(SqlRejected, match="That dataset is not enabled for this chat"):
        guard_sql("SELECT count(*) FROM ds_disabled", workspace_id=ws1_id, allowed_dataset_ids=[id1])

    # Querying completely non-existent table
    with pytest.raises(SqlRejected, match="is not accessible or does not exist"):
        guard_sql("SELECT count(*) FROM ds_nonexistent", workspace_id=ws1_id, allowed_dataset_ids=[id1])

    # Cleanup
    execute(f"DELETE FROM datasets WHERE id IN ({sql_id(id1)}, {sql_id(id2)})")


def test_get_schema_filters_allowed_datasets(test_workspaces):
    ws1_id, _ = test_workspaces
    up1 = make_test_upload(ws1_id, "s1.csv")
    up2 = make_test_upload(ws1_id, "s2.csv")
    ds1 = execute(
        f"INSERT INTO datasets (workspace_id, upload_id, table_name, table_label, grain) "
        f"VALUES ({sql_id(ws1_id)}, {sql_id(up1)}, 'ds_sch_1', 'Schema 1', 'Grain 1') RETURNING id"
    )
    ds2 = execute(
        f"INSERT INTO datasets (workspace_id, upload_id, table_name, table_label, grain) "
        f"VALUES ({sql_id(ws1_id)}, {sql_id(up2)}, 'ds_sch_2', 'Schema 2', 'Grain 2') RETURNING id"
    )
    id1 = ds1[0]["id"]
    id2 = ds2[0]["id"]

    schema_all = execute_schema(ws1_id, allowed_dataset_ids=[id1, id2])
    assert "ds_sch_1" in schema_all
    assert "ds_sch_2" in schema_all

    schema_filtered = execute_schema(ws1_id, allowed_dataset_ids=[id1])
    assert "ds_sch_1" in schema_filtered
    assert "ds_sch_2" not in schema_filtered

    execute(f"DELETE FROM datasets WHERE id IN ({id1}, {id2})")


def test_zero_dataset_selection_blocks_chat(test_workspaces):
    ws1_id, _ = test_workspaces
    client = TestClient(app)

    up = make_test_upload(ws1_id, "zero.csv")
    ds = execute(
        f"INSERT INTO datasets (workspace_id, upload_id, table_name, table_label, grain) "
        f"VALUES ({sql_id(ws1_id)}, {sql_id(up)}, 'ds_zero', 'Zero Data', 'Grain') RETURNING id"
    )
    ds_id = str(ds[0]["id"])

    # Create thread and uncheck all datasets
    update_thread_datasets(ws1_id, "empty-thread", [])

    # Client-sent dataset list is ignored; server checks thread's empty selection
    res = client.post(
        f"/workspaces/{ws1_id}/chat",
        json={"question": "What is total sales?", "thread_id": "empty-thread", "allowed_dataset_ids": [ds_id]},
    )
    assert res.status_code == 400
    assert "Select a dataset to ask about" in res.json()["detail"]

    execute(f"DELETE FROM datasets WHERE id = {sql_id(ds_id)}")


def test_remove_dataset_atomic(test_workspaces):
    ws1_id, _ = test_workspaces

    up = make_test_upload(ws1_id, "rem.csv")
    t_name = f"ds_rem_{str(ws1_id).replace('-', '_')}"
    # Create custom table in user_data
    execute(f"CREATE TABLE IF NOT EXISTS user_data.{t_name} (id int);")
    ds = execute(
        f"INSERT INTO datasets (workspace_id, upload_id, table_name, table_label, grain) "
        f"VALUES ({sql_id(ws1_id)}, {sql_id(up)}, '{t_name}', 'Remove Test', 'Grain') RETURNING id"
    )
    ds_id = str(ds[0]["id"])
    execute(f"INSERT INTO dataset_columns (dataset_id, column_name, source_name, type, role, description) VALUES ({sql_id(ds_id)}, 'id', 'ID', 'integer', 'identifier', 'ID')")
    execute(f"INSERT INTO quarantine (upload_id, row_number, reason, raw_json) VALUES ({sql_id(up)}, 1, 'bad format', '[]')")

    # Thread has this dataset selected
    update_thread_datasets(ws1_id, "t-remove", [ds_id])
    assert ds_id in get_or_create_thread(ws1_id, "t-remove")["selected_dataset_ids"]

    # Remove dataset
    res = remove_dataset(ws1_id, ds_id)
    assert res["ok"] is True

    # Check table is gone
    table_exists = execute(f"SELECT 1 FROM information_schema.tables WHERE table_schema = 'user_data' AND table_name = '{t_name}'")
    assert not table_exists

    # Check catalog rows are gone
    assert not execute(f"SELECT 1 FROM datasets WHERE id = {sql_id(ds_id)}")
    assert not execute(f"SELECT 1 FROM dataset_columns WHERE dataset_id = {sql_id(ds_id)}")
    assert not execute(f"SELECT 1 FROM quarantine WHERE upload_id = {sql_id(up)}")

    # Check thread selection has array_remove applied
    updated_t = get_or_create_thread(ws1_id, "t-remove")
    assert ds_id not in updated_t["selected_dataset_ids"]


def test_history_loader_filters_ghost_runs(test_workspaces):
    ws1_id, _ = test_workspaces

    # Insert a genuine Q&A run and a ghost run
    r1 = execute(
        f"INSERT INTO runs (workspace_id, question, answer, checker_result) "
        f"VALUES ({sql_id(ws1_id)}, 'Real question?', 'Real answer.', '{{\"thread_id\": \"clean-thread\"}}'::jsonb) RETURNING id"
    )
    r2 = execute(
        f"INSERT INTO runs (workspace_id, question, answer, checker_result) "
        f"VALUES ({sql_id(ws1_id)}, 'Schema Analysis', '{{\"table_label\": \"Ghost\"}}', '{{\"thread_id\": \"clean-thread\"}}'::jsonb) RETURNING id"
    )

    turns = get_turns(ws1_id, "clean-thread")
    assert len(turns) == 1
    assert turns[0]["question"] == "Real question?"
    assert turns[0]["answer"] == "Real answer."

    execute(f"DELETE FROM runs WHERE id IN ({sql_id(r1[0]['id'])}, {sql_id(r2[0]['id'])})")
