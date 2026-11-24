from __future__ import annotations

from app.agents.base import BaseAgent
from app.state import CaseState

ACTIONS = {
    "dependency_timeout": "检查下游依赖与连接池配置，必要时降级并启用超时重试",
    "resource_saturation": "扩容或限流，检查 CPU / 内存 / 连接池水位",
    "error_burst": "回滚最近变更，检查异常堆栈与配置项",
    "unknown": "人工介入，补充证据后再判定",
}


class ReporterAgent(BaseAgent):
    name = "reporter"

    def run(self, state: CaseState) -> dict:
        hypothesis = state["hypotheses"][0]
        evidences = [item for item in state["evidences"] if item.service == hypothesis.service]
        lines = [
            "# 告警研判报告",
            "",
            f"- Case：{state['case_id']}",
            f"- 告警：{state['alert'].get('title', '-')}",
            f"- 根因候选：**{hypothesis.service}**（置信度 {hypothesis.confidence:.0%}）",
            f"- 故障类型：{hypothesis.fault_type}",
            "",
            "## 研判说明",
            state.get("analysis") or "（无）",
            "",
            "## 证据链",
        ]
        for item in evidences:
            flag = " [injection-suspected]" if item.injected else ""
            lines.append(
                f"- [{item.source}] {item.service}（severity={item.severity:.2f}）{flag}：{item.summary}"
            )
        lines.extend(
            [
                "",
                "## 建议处置",
                f"- {ACTIONS.get(hypothesis.fault_type, ACTIONS['unknown'])}",
                "",
                "## 其他候选",
            ]
        )
        for item in state["hypotheses"][1:]:
            lines.append(f"- {item.service}（{item.fault_type}，置信度 {item.confidence:.0%}）")
        return {"report": "\n".join(lines), "step": state.get("step", 0) + 1}
