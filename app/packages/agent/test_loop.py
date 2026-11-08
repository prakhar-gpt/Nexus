"""The chat loop answers the golden questions and refuses the rest."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "app"))

from packages.agent.checker import extract_numbers  # noqa: E402
from packages.agent.loop import ask  # noqa: E402


def main() -> int:
    failures = []
    total = ask("What is total revenue?", 1)
    if total["kind"] != "sql" or not total["check"]["verified"]:
        failures.append("total revenue was not a verified SQL answer")
    if "2261536.78" not in total["answer"]:
        failures.append("total revenue value missing")
    if extract_numbers(total["answer"]) == []:
        failures.append("total revenue answer has no number")

    refused = ask("Which sub-categories lose money?", 1)
    if refused["kind"] != "refusal" or extract_numbers(refused["answer"]):
        failures.append("profit question was not refused without numbers")

    unknown = ask("What is the weather?", 1)
    if unknown["kind"] != "unknown" or unknown["sql"] is not None:
        failures.append("unknown question ran SQL")
    if extract_numbers(unknown["answer"]):
        failures.append("unknown answer contains a number")

    if failures:
        print("\n".join(failures))
        return 1
    print("loop ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
