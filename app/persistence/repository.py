from __future__ import annotations

import json
from datetime import datetime

from app.persistence.db import session_scope
from app.persistence.models import ApprovalRecord, RunRecord


def _run_to_dict(record: RunRecord) -> dict:
    return {
        "run_id": record.id,
        "case_id": record.case_id,
        "mode": record.mode,
        "root_cause": record.root_cause,
        "fault_type": record.fault_type,
        "confidence": record.confidence,
        "latency_ms": record.latency_ms,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


class RunRepository:
    def save(self, payload: dict) -> int:
        hypotheses = payload.get("hypotheses", [])
        first = hypotheses[0] if hypotheses else {}
        with session_scope() as session:
            record = RunRecord(
                case_id=payload.get("case_id", ""),
                mode=payload.get("mode", "multi"),
                root_cause=first.get("service", ""),
                fault_type=first.get("fault_type", ""),
                confidence=float(first.get("confidence", 0.0)),
                report=payload.get("report", ""),
                evidences_json=json.dumps(payload.get("evidences", []), ensure_ascii=False),
                hypotheses_json=json.dumps(hypotheses, ensure_ascii=False),
                latency_ms=float(payload.get("latency_ms", 0.0)),
            )
            session.add(record)
            session.flush()
            return record.id

    def list(self, limit: int = 50) -> list[dict]:
        with session_scope() as session:
            rows = (
                session.query(RunRecord)
                .order_by(RunRecord.id.desc())
                .limit(limit)
                .all()
            )
            return [_run_to_dict(row) for row in rows]

    def get(self, run_id: int) -> dict | None:
        with session_scope() as session:
            row = session.get(RunRecord, run_id)
            return _run_to_dict(row) if row else None


class ApprovalRepository:
    def save_start(self, thread_id: str, action: str, risk: str) -> None:
        with session_scope() as session:
            session.merge(
                ApprovalRecord(
                    thread_id=thread_id,
                    action=action,
                    risk=risk,
                    status="pending",
                )
            )

    def finish(self, thread_id: str, approved: bool) -> None:
        with session_scope() as session:
            record = session.get(ApprovalRecord, thread_id)
            if record is None:
                return
            record.status = "approved" if approved else "rejected"
            record.approved = approved

    def get(self, thread_id: str) -> dict | None:
        with session_scope() as session:
            record = session.get(ApprovalRecord, thread_id)
            if record is None:
                return None
            return {
                "thread_id": record.thread_id,
                "action": record.action,
                "risk": record.risk,
                "status": record.status,
                "approved": record.approved,
                "created_at": record.created_at.isoformat() if isinstance(record.created_at, datetime) else None,
            }
