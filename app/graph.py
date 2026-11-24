from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.agents.analyst import AnalystAgent
from app.agents.critic import CriticAgent
from app.agents.experts import LogsExpert, MetricsExpert, TracesExpert
from app.agents.llm_experts import LLMLogsExpert, LLMTracesExpert
from app.agents.reporter import ReporterAgent
from app.agents.supervisor import SupervisorAgent
from app.providers.base import LLMProvider
from app.state import CaseState
from app.tools.mock_sources import get_case

supervisor = SupervisorAgent()
metrics_expert = MetricsExpert()
logs_expert = LogsExpert()
traces_expert = TracesExpert()
reporter = ReporterAgent()


def load_case(state: CaseState) -> dict:
    case = get_case(state["case_id"])
    return {"alert": case["alert"], "inject_time": case.get("inject_time"), "step": 0}


def build_graph(
    mode: str = "multi",
    *,
    checkpointer=None,
    llm: LLMProvider | None = None,
    use_llm_experts: bool = False,
):
    """Build the RCA graph.

    Modes:
      multi      - three experts + causal ranking (default)
      no_causal  - three experts + plain weighted ranking (ablation)
      single     - metrics expert only (single-agent baseline)
    """
    if mode not in {"multi", "no_causal", "single"}:
        raise ValueError(f"unknown mode: {mode}")

    critic = CriticAgent(use_causal=(mode != "no_causal"))
    analyst = AnalystAgent(llm)
    logs_agent = LLMLogsExpert(llm) if use_llm_experts and llm is not None else logs_expert
    traces_agent = LLMTracesExpert(llm) if use_llm_experts and llm is not None else traces_expert

    graph = StateGraph(CaseState)
    graph.add_node("load_case", load_case)
    graph.add_node("supervisor", supervisor.run)
    graph.add_node("metrics", metrics_expert.run)
    graph.add_node("critic", critic.run)
    graph.add_node("analyst", analyst.run)
    graph.add_node("reporter", reporter.run)

    graph.add_edge(START, "load_case")
    graph.add_edge("load_case", "supervisor")
    graph.add_edge("supervisor", "metrics")
    graph.add_edge("metrics", "critic")

    if mode != "single":
        graph.add_node("logs", logs_agent.run)
        graph.add_node("traces", traces_agent.run)
        graph.add_edge("supervisor", "logs")
        graph.add_edge("supervisor", "traces")
        graph.add_edge("logs", "critic")
        graph.add_edge("traces", "critic")

    graph.add_edge("critic", "analyst")
    graph.add_edge("analyst", "reporter")
    graph.add_edge("reporter", END)

    return graph.compile(checkpointer=checkpointer)


def run_case(
    case_id: str,
    mode: str = "multi",
    *,
    llm: LLMProvider | None = None,
    use_llm_experts: bool = False,
    checkpointer=None,
    thread_id: str | None = None,
) -> CaseState:
    graph = build_graph(
        mode,
        checkpointer=checkpointer,
        llm=llm,
        use_llm_experts=use_llm_experts,
    )
    config = {"configurable": {"thread_id": thread_id or case_id}} if checkpointer else None
    return graph.invoke(
        {"case_id": case_id, "evidences": [], "step": 0, "usage": {}},
        config=config,
    )
