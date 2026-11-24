from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, Field


def merge_usage(left: dict[str, float], right: dict[str, float]) -> dict[str, float]:
    """Reducer for parallel agents that report token/cost usage."""
    keys = set(left) | set(right)
    return {key: left.get(key, 0.0) + right.get(key, 0.0) for key in keys}


class Evidence(BaseModel):
    """一条来自某个数据源的结构化证据。"""

    evidence_id: str
    source: Literal["metrics", "logs", "traces"]
    service: str
    summary: str
    severity: float = Field(ge=0.0, le=1.0)
    injected: bool = False


class Hypothesis(BaseModel):
    """Critic 给出的根因候选。"""

    service: str
    fault_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)


class CaseState(TypedDict, total=False):
    case_id: str
    alert: dict
    inject_time: float | None
    plan: list[str]
    evidences: Annotated[list[Evidence], operator.add]
    hypotheses: list[Hypothesis]
    critique: str
    analysis: str
    report: str
    approved: bool | None
    step: int
    usage: Annotated[dict[str, float], merge_usage]
