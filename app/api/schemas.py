from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CaseSummary(BaseModel):
    case_id: str
    title: str
    service: str
    severity: str
    root_cause: str
    fault_type: str


class EvidenceOut(BaseModel):
    evidence_id: str
    source: Literal["metrics", "logs", "traces"]
    service: str
    summary: str
    severity: float
    injected: bool


class HypothesisOut(BaseModel):
    service: str
    fault_type: str
    confidence: float
    evidence_ids: list[str]


class AnalyzeRequest(BaseModel):
    case_id: str = Field(min_length=1)
    mode: Literal["multi", "no_causal", "single"] = "multi"
    use_llm: bool = False


class AnalyzeResponse(BaseModel):
    case_id: str
    alert: dict
    report: str
    critique: str
    analysis: str
    evidences: list[EvidenceOut]
    hypotheses: list[HypothesisOut]
    usage: dict[str, float]
    latency_ms: float
    run_id: int | None = None


class RunSummary(BaseModel):
    run_id: int
    case_id: str
    mode: str
    root_cause: str
    fault_type: str
    confidence: float
    latency_ms: float
    created_at: str | None = None


class HealthResponse(BaseModel):
    status: str
    version: str


class ApprovalStartRequest(BaseModel):
    action: str = Field(min_length=1)
    risk: Literal["low", "medium", "high"] = "high"


class ApprovalStartResponse(BaseModel):
    thread_id: str
    status: str
    payload: dict | None = None


class ApprovalResumeRequest(BaseModel):
    approved: bool


class ApprovalResumeResponse(BaseModel):
    thread_id: str
    status: str
    approved: bool
