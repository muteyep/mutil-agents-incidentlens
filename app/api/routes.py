from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    ApprovalResumeRequest,
    ApprovalResumeResponse,
    ApprovalStartRequest,
    ApprovalStartResponse,
    CaseSummary,
    HealthResponse,
    RunSummary,
)
from app.persistence.repository import RunRepository
from app.services.analysis_service import analyze
from app.services.approval_service import ApprovalService
from app.services.case_service import CaseNotFoundError, get_case_summary, list_cases

router = APIRouter()
approvals = ApprovalService()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version="0.1.0")


@router.get("/api/cases", response_model=list[CaseSummary])
def cases() -> list[CaseSummary]:
    return [CaseSummary(**item) for item in list_cases()]


@router.get("/api/cases/{case_id}", response_model=CaseSummary)
def case(case_id: str) -> CaseSummary:
    try:
        return CaseSummary(**get_case_summary(case_id))
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"case not found: {case_id}") from exc


@router.post("/api/analyze", response_model=AnalyzeResponse)
def run_analysis(request: AnalyzeRequest) -> AnalyzeResponse:
    try:
        payload = analyze(request.case_id, mode=request.mode, use_llm=request.use_llm)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"case not found: {request.case_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AnalyzeResponse(**payload)


@router.get("/api/runs", response_model=list[RunSummary])
def runs(limit: int = 50) -> list[RunSummary]:
    return [RunSummary(**item) for item in RunRepository().list(limit)]


@router.get("/api/runs/{run_id}", response_model=RunSummary)
def run_detail(run_id: int) -> RunSummary:
    item = RunRepository().get(run_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
    return RunSummary(**item)


@router.post("/api/approval/start", response_model=ApprovalStartResponse)
def start_approval(request: ApprovalStartRequest) -> ApprovalStartResponse:
    return ApprovalStartResponse(**approvals.start(request.action, request.risk))


@router.post("/api/approval/{thread_id}/resume", response_model=ApprovalResumeResponse)
def resume_approval(thread_id: str, request: ApprovalResumeRequest) -> ApprovalResumeResponse:
    return ApprovalResumeResponse(**approvals.resume(thread_id, request.approved))
