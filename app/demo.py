from __future__ import annotations

import argparse

from app.graph import run_case
from app.providers.factory import build_llm
from app.tools.mock_sources import get_case


def main() -> None:
    parser = argparse.ArgumentParser(description="IncidentLens demo")
    parser.add_argument("case_id", nargs="?", default="case_001")
    parser.add_argument("--mode", default="multi", choices=["multi", "no_causal", "single"])
    parser.add_argument("--llm", action="store_true", help="use DeepSeek when DEEPSEEK_API_KEY is set")
    args = parser.parse_args()

    llm = build_llm() if args.llm else None
    if args.llm and llm is None:
        print("[warn] DEEPSEEK_API_KEY not set, falling back to rule-based analysis\n")

    result = run_case(args.case_id, mode=args.mode, llm=llm)

    print(result["report"])
    print("\n--- critic ---")
    print(result.get("critique", ""))
    print("\n--- ground truth ---")
    truth = get_case(args.case_id)["ground_truth"]
    print(f"root_cause_service={truth['root_cause_service']} fault_type={truth['fault_type']}")


if __name__ == "__main__":
    main()
