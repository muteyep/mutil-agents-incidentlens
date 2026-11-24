from __future__ import annotations

import json

from app.agents.base import BaseAgent
from app.agents.experts import LogsExpert, TracesExpert, _clamp
from app.guardrails.injection import scan
from app.providers.base import LLMError, LLMProvider
from app.registry import tool_registry
from app.state import CaseState, Evidence
from app.tools.mock_sources import list_services

LOG_SYSTEM = (
    "你是日志分析专家。只输出一个 JSON 对象，字段："
    'summary（不超过 80 字的中文结论）、severity（0 到 1 的浮点数）。'
)
TRACE_SYSTEM = (
    "你是链路分析专家。只输出一个 JSON 对象，字段："
    'summary（不超过 80 字的中文结论）、severity（0 到 1 的浮点数）。'
)


class _LLMExpert(BaseAgent):
    """LLM extracts a structured evidence summary; the caller fixes the service.

    The service name is never taken from the model, so a hallucinated entity
    cannot enter the evidence graph. Invalid JSON falls back to rules.
    """

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    def _extract(self, system: str, user: str, service: str, source: str, fallback: Evidence) -> tuple[Evidence, dict]:
        usage = {"prompt_tokens": 0.0, "completion_tokens": 0.0, "cost_usd": 0.0}
        try:
            response = self._llm.generate(
                [{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            payload = json.loads(response.content)
            summary = str(payload["summary"])[:200]
            severity = _clamp(float(payload["severity"]))
            usage = {
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
                "cost_usd": response.cost_usd,
            }
            return (
                Evidence(
                    evidence_id=f"ev-llm-{source}-{service}",
                    source=source,  # type: ignore[arg-type]
                    service=service,
                    summary=summary,
                    severity=severity,
                    injected=fallback.injected,
                ),
                usage,
            )
        except (LLMError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return fallback, usage


class LLMLogsExpert(_LLMExpert):
    name = "logs"

    def __init__(self, llm: LLMProvider) -> None:
        super().__init__(llm)
        self._fallback = LogsExpert()

    def run(self, state: CaseState) -> dict:
        case_id = state["case_id"]
        evidences: list[Evidence] = []
        usage = {"prompt_tokens": 0.0, "completion_tokens": 0.0, "cost_usd": 0.0}
        for service in list_services(case_id):
            logs = tool_registry.call("search_logs", case_id=case_id, service=service)
            if not logs:
                continue
            text = "\n".join(f"[{item.get('level')}] {item.get('message')}" for item in logs[:20])
            fallback = self._fallback.build(service, logs)
            evidence, call_usage = self._extract(
                LOG_SYSTEM, f"服务：{service}\n日志：\n{text}", service, "logs", fallback
            )
            evidences.append(evidence)
            for key, value in call_usage.items():
                usage[key] += value
        return {"evidences": evidences, "usage": usage}


class LLMTracesExpert(_LLMExpert):
    name = "traces"

    def __init__(self, llm: LLMProvider) -> None:
        super().__init__(llm)
        self._fallback = TracesExpert()

    def run(self, state: CaseState) -> dict:
        case_id = state["case_id"]
        evidences: list[Evidence] = []
        usage = {"prompt_tokens": 0.0, "completion_tokens": 0.0, "cost_usd": 0.0}
        for service in list_services(case_id):
            spans = tool_registry.call("get_traces", case_id=case_id, service=service)
            if not spans:
                continue
            text = json.dumps(spans, ensure_ascii=False)
            fallback = self._fallback.build(service, spans)
            evidence, call_usage = self._extract(
                TRACE_SYSTEM, f"服务：{service}\n链路：{text}", service, "traces", fallback
            )
            evidences.append(evidence)
            for key, value in call_usage.items():
                usage[key] += value
        return {"evidences": evidences, "usage": usage}


__all__ = ["LLMLogsExpert", "LLMTracesExpert", "scan"]
