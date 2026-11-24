from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from ui.client import ApiError, IncidentLensClient

st.set_page_config(page_title="IncidentLens", page_icon="🚨", layout="wide")
st.title("IncidentLens · 多智能体故障根因分析")

base_url = st.sidebar.text_input(
    "API 地址",
    os.getenv("INCIDENTLENS_API_URL", "http://localhost:8000"),
)
client = IncidentLensClient(base_url)

try:
    client.health()
except ApiError as exc:
    st.error(f"API 未连接：{exc}")
    st.code("uvicorn app.api.app:app --port 8000", language="bash")
    st.stop()

cases = client.list_cases()
case_ids = [item["case_id"] for item in cases]
case_id = st.sidebar.selectbox("选择 case", case_ids, index=0)
mode = st.sidebar.radio("运行模式", ["multi", "no_causal", "single"], index=0)
use_llm = st.sidebar.checkbox("使用 LLM 专家（需 API Key）", value=False)

if st.sidebar.button("开始研判", type="primary"):
    with st.spinner("三路专家取证中..."):
        try:
            st.session_state["result"] = client.analyze(case_id, mode, use_llm)
        except ApiError as exc:
            st.error(f"研判失败：{exc}")

result = st.session_state.get("result")
if result:
    st.subheader(result["alert"].get("title", result["case_id"]))
    st.caption(
        f"case={result['case_id']} · latency={result['latency_ms']}ms · "
        f"mode={mode}"
    )
    st.markdown(result["report"])

    st.subheader("证据")
    st.dataframe(result["evidences"], use_container_width=True)

    st.subheader("候选排序")
    st.code(result.get("critique", ""), language="text")

    st.subheader("处置审批（HITL）")
    hypothesis = result["hypotheses"][0]
    action = f"{hypothesis['fault_type']} → {hypothesis['service']}"
    st.write(f"建议动作：{action}")

    if st.button("发起审批"):
        try:
            st.session_state["approval"] = client.start_approval(action, "high")
        except ApiError as exc:
            st.error(f"发起审批失败：{exc}")

    approval = st.session_state.get("approval")
    if approval:
        st.json(approval)
        col1, col2 = st.columns(2)
        if col1.button("批准"):
            st.success(client.resume_approval(approval["thread_id"], True))
        if col2.button("拒绝"):
            st.warning(client.resume_approval(approval["thread_id"], False))

    st.subheader("最近运行")
    st.dataframe(client.list_runs(10), use_container_width=True)
else:
    st.info("左侧选择 case，点击「开始研判」。")
