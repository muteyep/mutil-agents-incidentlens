# Architecture

```
                    ┌─────────────────────────────┐
   alert / case ───▶│ load_case                    │
                    └──────────────┬──────────────┘
                                   ▼
                    ┌─────────────────────────────┐
                    │ Supervisor（只调度，不查数据）│
                    └───┬──────────┬──────────┬───┘
                        ▼          ▼          ▼
                  ┌─────────┐ ┌─────────┐ ┌─────────┐
                  │ Metrics │ │  Logs   │ │ Traces  │   ← 三路并行
                  └────┬────┘ └────┬────┘ └────┬────┘
                       └───────────┼───────────┘
                                   ▼
                    ┌─────────────────────────────┐
                    │ Critic                       │
                    │ 证据加权 + 因果惩罚           │
                    │ root = self - 0.5 * callee   │
                    └──────────────┬──────────────┘
                                   ▼
                    ┌─────────────────────────────┐
                    │ Analyst（LLM 只解释，不定因） │
                    └──────────────┬──────────────┘
                                   ▼
                    ┌─────────────────────────────┐
                    │ Reporter（报告 + 证据链）     │
                    └─────────────────────────────┘
```

## 关键决策

1. **LLM 取证，规则定因**：LLM 不参与最终排序，避免"让模型拍脑袋"。
2. **因果惩罚**：`root = self - 0.5 * max(callee)`，消除"调用方症状更明显"的 victim bias。
3. **证据结构化**：所有专家返回 `Evidence`，不是自由文本，便于聚合与评测。
4. **注入防护**：日志中出现 "ignore previous instructions" 等模式会被标记并降权，不改变结论。
5. **并行**：三路专家并行执行，`evidences` 用 reducer 累加；专家不能写 `step`（会触发并发更新冲突）。

## 失败模式

| 现象 | 原因 | 处理 |
|---|---|---|
| `INVALID_CONCURRENT_GRAPH_UPDATE` | 并行节点写同一个非 reducer 字段 | 只让并行节点写 `evidences` |
| 根因被调用方抢走 | 调用方错误率更高 | 因果惩罚（callee 异常则降权） |
| 日志注入改变结论 | 检索内容当指令 | 注入扫描 + 降权 + 标记 |
| 长任务中断 | 无 checkpoint | `SqliteSaver` + `thread_id` |
| 高风险动作误执行 | 无 HITL | `interrupt()` + `Command(resume=...)` |

## LLM 层

```
LLMLogsExpert / LLMTracesExpert
  → LLMProvider.generate(response_format=json_object)
  → json.loads + Pydantic Evidence
  → 失败回退规则版
  → usage(prompt_tokens / completion_tokens / cost_usd) 写入 reducer
```

- 服务名由调用方固定，模型不能编造实体。
- LLM 只产出 `summary` 与 `severity`，不参与根因排序。
- `AnalystAgent` 只生成解释，根因已由 `causal.py` 决定。

## 评测层

- `eval/runner.py`：multi / single / no_causal / multi_llm 四组对照。
- `eval/stats.py`：1000 次 Bootstrap，报 R@1 与 MRR 的 95% CI。
- `eval/rcaeval_adapter.py`：把 RCAEval 的 metrics/logs/traces 转成本项目 case。
- 成本：从 `state["usage"]` 汇总，按 provider 单价折算。
