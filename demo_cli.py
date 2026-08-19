import argparse
import json
import uuid

from langgraph.types import Command

from src.sample_data import SAMPLE_CONFLICT, SAMPLE_HIGH_VALUE, SAMPLE_STANDARD
from src.workflow import GRAPH

SAMPLES = {
    "standard": SAMPLE_STANDARD,
    "high": SAMPLE_HIGH_VALUE,
    "conflict": SAMPLE_CONFLICT,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", choices=SAMPLES, default="high")
    args = parser.parse_args()

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    result = GRAPH.invoke(
        {"raw_text": SAMPLES[args.sample], "document_id": f"CLI-{thread_id[:8]}"},
        config=config,
    )
    print(json.dumps(result, indent=2, default=str))

    if result.get("__interrupt__"):
        print("\n--- HITL PAUSE ---")
        print(result.get("exception_summary", ""))
        decision = input("Decision [APPROVE/REJECT]: ").strip().upper() or "REJECT"
        notes = input("Reviewer notes: ").strip()
        result = GRAPH.invoke(Command(resume={"decision": decision, "notes": notes}), config=config)
        print("\n--- RESUMED ---")
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
