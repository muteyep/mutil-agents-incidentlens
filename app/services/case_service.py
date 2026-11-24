from __future__ import annotations

import json
from pathlib import Path

from app.tools.mock_sources import DATA_DIR


class CaseNotFoundError(KeyError):
    """Raised when a case id does not exist on disk."""


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def list_cases(data_dir: Path = DATA_DIR) -> list[dict]:
    items: list[dict] = []
    for path in sorted(data_dir.glob("*.json")):
        case = _load(path)
        truth = case.get("ground_truth", {})
        items.append(
            {
                "case_id": case.get("case_id", path.stem),
                "title": case.get("alert", {}).get("title", ""),
                "service": case.get("alert", {}).get("service", ""),
                "severity": case.get("alert", {}).get("severity", ""),
                "root_cause": truth.get("root_cause_service", ""),
                "fault_type": truth.get("fault_type", ""),
            }
        )
    return items


def get_case_summary(case_id: str, data_dir: Path = DATA_DIR) -> dict:
    path = data_dir / f"{case_id}.json"
    if not path.exists():
        raise CaseNotFoundError(case_id)
    case = _load(path)
    truth = case.get("ground_truth", {})
    return {
        "case_id": case.get("case_id", case_id),
        "title": case.get("alert", {}).get("title", ""),
        "service": case.get("alert", {}).get("service", ""),
        "severity": case.get("alert", {}).get("severity", ""),
        "root_cause": truth.get("root_cause_service", ""),
        "fault_type": truth.get("fault_type", ""),
    }
