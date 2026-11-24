from __future__ import annotations

from pathlib import Path

from eval.rcaeval_adapter import load_rcaeval_case, prepare_dataset

FIXTURE = Path(__file__).resolve().parents[1] / "data" / "rcaeval_fixture"


def test_load_rcaeval_fixture_case() -> None:
    case = load_rcaeval_case(FIXTURE / "case_a")
    assert case["case_id"] == "re_case_a"
    assert case["alert"]["service"] == "checkout"
    assert case["ground_truth"]["root_cause_service"] == "payment"
    assert case["ground_truth"]["fault_type"] == "dependency_timeout"
    assert case["services"]["payment"]["metrics"][0]["p99_ms"] == 4800
    assert case["services"]["checkout"]["logs"][0]["level"] == "ERROR"
    assert case["services"]["payment"]["traces"][0]["error_rate"] == 0.31


def test_prepare_dataset_writes_all_cases(tmp_path: Path) -> None:
    written = prepare_dataset(FIXTURE, tmp_path, limit=10)
    assert len(written) == 2
    assert {path.name for path in written} == {"re_case_a.json", "re_case_b.json"}


def test_converted_cases_run_through_graph() -> None:
    from app.graph import run_case

    case = load_rcaeval_case(FIXTURE / "case_a")
    out = tmp_path_case(case)
    result = run_case(out["case_id"])
    assert result["hypotheses"][0].service == "payment"


def tmp_path_case(case: dict) -> dict:
    """Write a converted case into data/cases so tools can load it."""
    import json

    from app.tools.mock_sources import DATA_DIR

    path = DATA_DIR / f"{case['case_id']}.json"
    path.write_text(json.dumps(case, ensure_ascii=False), encoding="utf-8")
    return case
