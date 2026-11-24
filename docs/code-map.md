# 代码阅读地图（7 天）

> 目标：读完能脱稿讲 30 分钟，并把每条 bullet 对应到文件。

## 阅读原则

1. 不逐行读：先跑，再读核心函数，最后改一个参数。
2. 读懂标准：关掉代码能讲 2 分钟。
3. `eval/` 只看入口函数，`tests/` 只看 3 个。

## 计划

| Day | 文件 | 行数 | 要能回答 | 简历产出 |
|---|---|---|---|---|
| D1 | `app/state.py`、`app/tools/mock_sources.py`、`data/cases/case_001.json`、`app/demo.py` | ~130 | case 数据结构、Evidence 字段 | 项目定位 |
| D2 | `app/registry.py`、`app/agents/experts.py` | ~157 | 三个专家 severity 公式、z-score 取舍 | 多源取证 |
| D3 | `app/analysis/causal.py`、`app/agents/critic.py` | ~142 | 因果公式、为什么 `-0.5×callee` | 算法 bullet |
| D4 | `app/graph.py`、`app/agents/base.py`、`supervisor.py`、`analyst.py`、`reporter.py` | ~208 | 并行 reducer、为什么不能写 step | 编排 bullet |
| D5 | `app/runtime.py`、`app/hitl.py`、`app/governance/budget.py`、`loop_guard.py` | ~147 | checkpoint、interrupt/resume | 可靠性 bullet |
| D6 | `eval/runner.py`、`eval/stats.py`、`eval/generate_cases.py` | ~274 | R@1/MRR/CI、三组消融 | 评测 bullet |
| D7 | `app/guardrails/injection.py`、`app/providers/*`、`app/agents/llm_experts.py`、`eval/rcaeval_adapter.py` 两个入口 | ~400 | 注入、LLM 校验、RCAEval 转换 | 安全 + 真实数据 |

## 必精读 6 个文件

- `app/analysis/causal.py`（65 行）
- `app/agents/critic.py`（77 行）
- `app/agents/experts.py`（130 行）
- `app/graph.py`（96 行）
- `app/runtime.py`（43 行）+ `app/hitl.py`（32 行）
- `eval/runner.py`（149 行）

## 三个动手练习

1. 改 `WEIGHTS`：`metrics .6 / logs .2 / traces .2`，重跑 `python -m eval.runner`。
2. 把 `root_score = own - 0.5 * callee_max` 改成 `own`，观察 R@1 掉到接近 `no_causal`。
3. 复制 `case_001.json` 改成 `case_004`，根因设为 `db`，跑 `python -m app.demo case_004`。

## 10 个自测问题

1. 一条 case 从 JSON 到报告经过哪些节点？
2. 三个专家的 severity 公式？
3. 为什么点数多时用 z-score？
4. 因果排序公式和直觉？
5. 为什么并行节点不能写 `step`？
6. `thread_id` 解决什么？
7. `interrupt` 与 `Command(resume=...)` 怎么配合？
8. 注入证据为什么降权而不是删除？
9. R@1、MRR、95% CI 的口径？
10. `single` 和 `no_causal` 分别在证明什么？

## 代码 → 简历 bullet 映射

| Bullet | 对应代码 |
|---|---|
| 架构 | `graph.py`、`supervisor.py`、`experts.py` |
| 算法 | `causal.py`、`critic.py` |
| 可靠性 | `runtime.py`、`hitl.py`、`governance/*` |
| 安全 | `guardrails/injection.py`、`tests/test_injection.py` |
| 评测 | `eval/runner.py`、`eval/stats.py`、`eval/rcaeval_adapter.py` |

## 可选：API 层（约 250 行）

- `app/api/schemas.py`：请求/响应模型
- `app/api/routes.py`：6 个端点
- `app/api/app.py`：create_app
- `app/services/case_service.py` / `analysis_service.py` / `approval_service.py`
- `tests/api/test_api.py`：8 个 API 测试

读完后能回答：为什么审批图用 MemorySaver？生产要换成什么？


## 可选：真实遥测 / 持久化 / UI（约 900 行）

- `app/telemetry/prometheus.py` / `loki.py` / `tempo.py`：HTTP 客户端
- `app/telemetry/live.py`：实时数据转 case
- `app/persistence/db.py` / `models.py` / `repository.py`：SQLAlchemy
- `ui/client.py`：HTTP 客户端
- `ui/app.py`：Streamlit 走 API

读完后能回答：为什么 live case 没有 ground truth？MemorySaver 和 DB 记录的区别？


## 可选：真实数据（约 300 行）

- `eval/download_hf_cases.py`：HuggingFace 逐条下载
- `eval/hf_adapter.py`：parquet → case，含 Online Boutique 拓扑
- 读完能回答：为什么 traces 没全量下载？ground truth 从哪来？
