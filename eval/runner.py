"""Evaluation harness.

Usage:
    python -m eval.generate_cases
    python -m eval.runner                 # rule-based multi/single/no_causal
    python -m eval.runner --llm           # adds multi_llm (needs DEEPSEEK_API_KEY)
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from app.graph import run_case
from app.providers.factory import build_llm
from eval.stats import bootstrap_ci

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "cases"
REPORT_PATH = Path(__file__).resolve().parent / "report.json"


@dataclass
class CaseResult:
    case_id: str
    mode: str
    predicted: str
    truth: str
    fault_type: str
    truth_fault: str
    rank: int
    latency_ms: float
    cost_usd: float
    hit1: bool
    hit3: bool
    reciprocal_rank: float
    fault_correct: bool


def load_cases(data_dir: Path = DATA_DIR, filter_prefix: str = "") -> list[dict]:
    cases = []
    for path in sorted(data_dir.glob("*.json")):
        if filter_prefix and not path.stem.startswith(filter_prefix):
            continue
        cases.append(json.loads(path.read_text(encoding="utf-8")))
    return cases


def run_mode(
    mode: str,
    llm=None,
    data_dir: Path = DATA_DIR,
    filter_prefix: str = "",
) -> list[CaseResult]:
    results: list[CaseResult] = []
    for case in load_cases(data_dir, filter_prefix):
        started = time.perf_counter()
        state = run_case(
            case["case_id"],
            mode="multi" if mode == "multi_llm" else mode,
            llm=llm,
            use_llm_experts=(mode == "multi_llm"),
        )
        latency = (time.perf_counter() - started) * 1000
        ranked = [item.service for item in state["hypotheses"]]
        truth = case["ground_truth"]["root_cause_service"]
        rank = ranked.index(truth) + 1 if truth in ranked else 99
        results.append(
            CaseResult(
                case_id=case["case_id"],
                mode=mode,
                predicted=ranked[0] if ranked else "unknown",
                truth=truth,
                fault_type=state["hypotheses"][0].fault_type,
                truth_fault=case["ground_truth"]["fault_type"],
                rank=rank,
                latency_ms=round(latency, 2),
                cost_usd=round(float(state.get("usage", {}).get("cost_usd", 0.0)), 6),
                hit1=rank == 1,
                hit3=rank <= 3,
                reciprocal_rank=round(1 / rank, 4) if rank != 99 else 0.0,
                fault_correct=state["hypotheses"][0].fault_type
                == case["ground_truth"]["fault_type"],
            )
        )
    return results


def summarize(results: list[CaseResult]) -> dict:
    total = len(results)
    hit1 = [1.0 if item.hit1 else 0.0 for item in results]
    rr = [item.reciprocal_rank for item in results]
    low1, high1, mean1 = bootstrap_ci(hit1)
    lowm, highm, meanm = bootstrap_ci(rr)
    return {
        "cases": total,
        "r_at_1": round(mean1, 4),
        "r_at_1_ci": [low1, high1],
        "r_at_3": round(sum(item.hit3 for item in results) / total, 4),
        "mrr": round(meanm, 4),
        "mrr_ci": [lowm, highm],
        "fault_accuracy": round(sum(item.fault_correct for item in results) / total, 4),
        "avg_latency_ms": round(sum(item.latency_ms for item in results) / total, 2),
        "total_cost_usd": round(sum(item.cost_usd for item in results), 6),
        "cost_per_case_usd": round(sum(item.cost_usd for item in results) / total, 6),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="IncidentLens evaluation")
    parser.add_argument("--llm", action="store_true", help="add the multi_llm mode")
    parser.add_argument("--data-dir", default=DATA_DIR, type=Path, help="case directory")
    parser.add_argument("--filter", default="", help="only case ids with this prefix")
    parser.add_argument("--report", default=REPORT_PATH, type=Path)
    args = parser.parse_args()

    llm = build_llm() if args.llm else None
    if args.llm and llm is None:
        raise SystemExit("DEEPSEEK_API_KEY is required for --llm")

    modes = ["multi", "single", "no_causal"]
    if llm is not None:
        modes.append("multi_llm")

    all_results: dict[str, list[CaseResult]] = {}
    summary: dict[str, dict] = {}
    for mode in modes:
        results = run_mode(
            mode, llm=llm, data_dir=args.data_dir, filter_prefix=args.filter
        )
        all_results[mode] = results
        summary[mode] = summarize(results)

    header = (
        f"{'mode':<12}{'cases':>6}{'R@1':>8}{'95% CI':>18}"
        f"{'R@3':>8}{'MRR':>8}{'Fault':>8}{'Avg ms':>10}{'$/case':>10}"
    )
    print(header)
    print("-" * len(header))
    for mode, metrics in summary.items():
        ci = f"[{metrics['r_at_1_ci'][0]:.2f}, {metrics['r_at_1_ci'][1]:.2f}]"
        print(
            f"{mode:<12}{metrics['cases']:>6}{metrics['r_at_1']:>8.2%}{ci:>18}"
            f"{metrics['r_at_3']:>8.2%}{metrics['mrr']:>8.2f}"
            f"{metrics['fault_accuracy']:>8.2%}{metrics['avg_latency_ms']:>10.1f}"
            f"{metrics['cost_per_case_usd']:>10.4f}"
        )

    payload = {
        "summary": summary,
        "results": {mode: [asdict(item) for item in items] for mode, items in all_results.items()},
    }
    args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nreport written to {args.report}")


if __name__ == "__main__":
    main()
