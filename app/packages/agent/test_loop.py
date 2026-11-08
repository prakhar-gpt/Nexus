"""The agent chooses tools, and a later turn can see the earlier one."""

from __future__ import annotations

import sys
from pathlib import Path

from langchain_core.messages import AIMessage, AIMessageChunk

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "app"))

from packages.agent.graph import MAX_TOOL_STEPS, Agent, GRAPH, _chunk_text  # noqa: E402


class Scripted:
    def __init__(self, replies):
        self.replies = list(replies)
        self.seen = []

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self.seen.append(messages)
        return self.replies.pop(0)


def _call(name: str, args: dict, call_id: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}],
    )


def main() -> int:
    edges = {(edge.source, edge.target) for edge in GRAPH.graph.get_graph().edges}
    if ("tools", "agent") not in edges or ("agent", "tools") not in edges:
        print("FAIL the agent cannot return to itself")
        return 1

    revenue = Scripted(
        [
            _call(
                "run_sql",
                {"sql": "SELECT round(sum(revenue), 2) AS total_revenue FROM sales_clean"},
                "rev",
            ),
            AIMessage(content="total_revenue=2261536.78"),
        ]
    )
    result = Agent(revenue).ask("What is total revenue?", 1, thread_id="loop-revenue", history=[])
    if "2261536.78" not in result["answer"] or not result["check"]["verified"]:
        print("FAIL revenue", result["answer"], result["check"])
        return 1
    if [step["tool"] for step in result["steps"]][:1] != ["run_sql"]:
        print("FAIL the agent did not choose run_sql", result["steps"])
        return 1

    blocked = Scripted(
        [
            _call("run_sql", {"sql": "DELETE FROM sales_clean"}, "bad"),
            AIMessage(content="Cannot answer. The query was rejected."),
        ]
    )
    rejected = Agent(blocked).ask("Delete the rows.", 1, thread_id="loop-guard", history=[])
    tool_text = blocked.seen[1][-1].content
    if not str(tool_text).startswith("rejected") or rejected["sql"] is not None:
        print("FAIL guard", tool_text, rejected["sql"])
        return 1
    if any(char.isdigit() for char in rejected["answer"]):
        print("FAIL refusal leaked a number", rejected["answer"])
        return 1

    first = Scripted([AIMessage(content="West leads on revenue.")])
    second = Scripted([AIMessage(content="East is the follow-up.")])
    thread = Agent(first)
    thread.model = first
    thread.ask("Which region leads?", 1, thread_id="loop-history", history=[])
    thread.model = second
    thread.ask("And the East?", 1, thread_id="loop-history", history=[])
    flat = " ".join(str(message.content) for message in second.seen[0])
    if "Which region leads?" not in flat or "West leads on revenue." not in flat:
        print("FAIL history was not in the next turn", flat)
        return 1

    spinning = Scripted(
        [_call("get_schema", {}, f"spin-{index}") for index in range(MAX_TOOL_STEPS + 2)]
    )
    capped = Agent(spinning).ask("Keep going.", 1, thread_id="loop-cap", history=[])
    tool_steps = [step for step in capped["steps"] if step["tool"] == "get_schema"]
    if len(tool_steps) != MAX_TOOL_STEPS or "step limit" not in capped["answer"]:
        print("FAIL step cap", len(tool_steps), capped["answer"])
        return 1

    live = Scripted(
        [
            _call(
                "run_sql",
                {"sql": "SELECT round(sum(revenue), 2) AS total_revenue FROM sales_clean"},
                "live",
            ),
            AIMessage(content="total_revenue=2261536.78"),
        ]
    )
    streamed = list(Agent(live).watch("What is total revenue?", 1, thread_id="loop-stream", history=[]))
    statuses = [item[1]["status"] for item in streamed if item[0] == "step"]
    if statuses[:2] != ["running", "ok"]:
        print("FAIL tool status did not stream", statuses)
        return 1
    tokens = [item[1] for item in streamed if item[0] == "token"]
    if not any("2261536.78" in str(token) for token in tokens):
        print("FAIL the answer was not streamed", tokens)
        return 1
    spaced = _chunk_text(AIMessageChunk(content=" revenue"))
    if spaced != " revenue":
        print("FAIL a streamed token lost its space", repr(spaced))
        return 1

    print("loop ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
