"""Upload, confirm, chat, and export against the live database."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

import main as api  # noqa: E402
from main import app  # noqa: E402
from ingest.store import execute, sql_literal  # noqa: E402

FIXTURES = ROOT / "datasets" / "tests"
FAILURES = []


def check(name: str, ok: bool, detail: str = "") -> None:
    if ok:
        print(f"pass {name}")
        return
    FAILURES.append(f"{name} {detail}".strip())
    print(f"FAIL {name} {detail}".strip())


def room_id() -> int:
    found = execute("SELECT id FROM workspaces WHERE name = 'API tests' ORDER BY id LIMIT 1")
    if found:
        return int(found[0]["id"])
    created = execute(
        f"INSERT INTO workspaces (name) VALUES ({sql_literal('API tests')}) RETURNING id"
    )
    return int(created[0]["id"])


def main() -> int:
    client = TestClient(app)
    rooms = client.get("/workspaces")
    check("list rooms", rooms.status_code == 200 and any(item["name"] == "Superstore" for item in rooms.json()))

    detail = client.get("/workspaces/1")
    body = detail.json()
    check(
        "superstore health",
        detail.status_code == 200 and body["health"]["rows"] == "9800",
        str(body.get("health")),
    )

    api.stream = lambda question, workspace_id: iter(
        [
            (
                "step",
                {
                    "id": "rev",
                    "tool": "run_sql",
                    "status": "running",
                    "detail": "Running a query…",
                },
            ),
            ("token", "total_revenue="),
            ("token", "2261536.78"),
            (
                "result",
                {
                    "kind": "sql",
                    "plan": "run_sql, checker",
                    "sql": "SELECT round(sum(revenue), 2) AS total_revenue FROM sales_clean",
                    "rows": [{"total_revenue": "2261536.78"}],
                    "answer": "total_revenue=2261536.78",
                    "check": {"verified": True, "untraced": []},
                    "steps": [{"tool": "run_sql", "status": "ok", "ms": 1}],
                    "latency_ms": 1,
                    "model": "test",
                },
            ),
        ]
    )
    with client.stream(
        "POST",
        "/workspaces/1/chat",
        json={"question": "What is total revenue?"},
    ) as response:
        text = response.read().decode()
    check("chat stream", "event: check" in text and "2261536.78" in text and '"verified": true' in text)
    done = text.split("event: done\n", 1)[-1]
    payload = json.loads(done.split("data: ", 1)[1].strip())
    exported = client.get(f"/results/{payload['run_id']}/export")
    check("export", exported.status_code == 200 and b"2261536.78" in exported.content)
    again = client.get("/workspaces/1")
    turns = again.json().get("turns") or []
    check(
        "chat history",
        any(item.get("question") == "What is total revenue?" for item in turns),
        str(len(turns)),
    )

    room = room_id()
    payroll = FIXTURES / "05_payroll.csv"
    uploaded = client.post(
        f"/workspaces/{room}/uploads",
        files={"file": ("05_payroll.csv", payroll.read_bytes(), "text/csv")},
    )
    upload_id = uploaded.json().get("upload_id")
    events = client.get(f"/uploads/{upload_id}/events")
    check(
        "payroll rejected",
        uploaded.status_code == 200 and "missing" in events.text and "event: done" in events.text,
        events.text[-400:],
    )

    messy = client.post(
        f"/workspaces/{room}/uploads",
        files={"file": ("03_messy.csv", (FIXTURES / "03_messy.csv").read_bytes(), "text/csv")},
    )
    messy_id = messy.json()["upload_id"]
    messy_events = client.get(f"/uploads/{messy_id}/events").text
    check("messy waits", "needs_confirmation" in messy_events, messy_events[-400:])
    done_payload = json.loads(messy_events.split("event: done\ndata: ", 1)[1].strip())
    decisions = {
        item["source"]: item["canonical"]
        for item in done_payload["mappings"]
        if item["needs_confirmation"] and item["canonical"]
    }
    confirmed = client.put(f"/uploads/{messy_id}/mapping", json={"decisions": decisions})
    check(
        "messy confirmed",
        confirmed.status_code == 200 and confirmed.json()["status"] == "accepted",
        str(confirmed.json()),
    )

    if FAILURES:
        print(f"failures={len(FAILURES)}")
        return 1
    print("failures=0")
    return 0


if __name__ == "__main__":
    sys.exit(main())


def test_api_endpoints():
    assert main() == 0
