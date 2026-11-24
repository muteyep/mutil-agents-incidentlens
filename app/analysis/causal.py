"""Causal-style ranking over an evidence graph.

The LLM's job is to gather evidence, not to decide the root cause. This
module turns per-service evidence scores plus the service dependency graph
into a deterministic, explainable ranking:

    root_score(service) = self_score - 0.5 * max(self_score(callee))

Intuition: an anomalous caller with an even more anomalous callee is a
victim, not the root cause. The penalty removes that victim bias.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from app.state import Evidence

WEIGHTS = {"metrics": 0.4, "logs": 0.3, "traces": 0.3}


@dataclass(frozen=True)
class RankedCause:
    service: str
    score: float
    self_score: float
    callee_max: float


def self_scores(evidences: list[Evidence]) -> dict[str, float]:
    scores: dict[str, float] = defaultdict(float)
    for evidence in evidences:
        scores[evidence.service] += WEIGHTS[evidence.source] * evidence.severity
    return dict(scores)


def rank_root_causes(
    evidences: list[Evidence],
    topology: dict[str, list[str]],
) -> list[RankedCause]:
    scores = self_scores(evidences)
    ranked: list[RankedCause] = []
    for service, own in scores.items():
        callees = topology.get(service, [])
        callee_max = max((scores.get(callee, 0.0) for callee in callees), default=0.0)
        root_score = own - 0.5 * callee_max
        ranked.append(
            RankedCause(
                service=service,
                score=root_score,
                self_score=own,
                callee_max=callee_max,
            )
        )
    ranked.sort(key=lambda item: (-item.score, item.service))
    return ranked


def weighted_ranking(evidences: list[Evidence]) -> list[RankedCause]:
    scores = self_scores(evidences)
    return [
        RankedCause(service=service, score=score, self_score=score, callee_max=0.0)
        for service, score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    ]
