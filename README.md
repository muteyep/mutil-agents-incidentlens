# IncidentLens

多智能体故障根因分析系统（Multi-Agent RCA）。一条告警进入后，三路专家并行取证，Critic 用**确定性因果排序**定位根因，Analyst 只负责解释，Reporter 输出带证据链的报告。

> 独立 Python 实现。编排思路参考了公开的多 Agent RCA 工作（RCLAgent、aiops-rca）与课程架构，未复制任何课程源码。

---

## 架构

```
load_case → Supervisor
              ├── Metrics 专家 ─┐
              ├── Logs 专家    ├─→ Critic（因果排序）→ Analyst → Reporter
              └── Traces 专家  ─┘
```

### 关键设计

| 决策 | 原因 |
|---|---|
| **LLM 取证，规则定因** | 根因排序不交给 LLM，避免"拍脑袋"和不可复现 |
| **因果惩罚** | `root = self - 0.5 × max(callee)`，消除"调用方症状更明显"的 victim bias |
| **结构化证据** | 所有专家返回 `Evidence`，便于聚合、评测和审计 |
| **LLM 专家可选** | 日志/链路可用 LLM 抽取摘要；服务名由调用方固定，模型不能编造实体 |
| **注入防护** | 日志中的 "ignore previous instructions" 会被标记并降权 |
| **并行 reducer** | 三路专家只写 `evidences` / `usage`，避免 LangGraph 并发更新冲突 |
| **Checkpoint + HITL** | `SqliteSaver` 支持断点续跑；`interrupt()` 支持高风险动作审批 |

---

## 快速开始

```bash
cd incidentlens
python3 -m venv .venv
source .venv/bin/activate

# 国内网络建议用镜像
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -e ".[dev]"

pytest -q                     # 56 passed
python -m app.demo case_001   # 单条 case
python -m app.demo_hitl       # HITL 中断/恢复演示

python -m eval.generate_cases # 生成 12 条合成评测 case
python -m eval.runner         # multi / single / no_causal + Bootstrap CI

# 可选：LLM 专家 + LLM 解释（没有 key 自动回退规则版）
export DEEPSEEK_API_KEY=...
python -m app.demo case_001 --llm
python -m eval.runner --llm   # 增加 multi_llm 模式

# 可选：Streamlit UI
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -e ".[ui]"
streamlit run ui/app.py
```

---

## 真实遥测

```bash
export PROMETHEUS_URL=http://localhost:9090
export LOKI_URL=http://localhost:3100
export TEMPO_URL=http://localhost:3200

python -m app.telemetry.live --service checkout --services checkout,payment --window 15
```

- `PrometheusClient`：p99 / error / cpu
- `LokiClient`：level / message
- `TempoClient`：span p99
- `build_live_case()` 把实时数据转成 case，复用同一套 Agent 图

详见 `docs/telemetry.md`。

## HTTP API

```bash
uvicorn app.api.app:app --reload --port 8000
# Swagger: http://localhost:8000/docs
```

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 健康检查 |
| GET | `/api/cases` | case 列表 |
| GET | `/api/cases/{case_id}` | case 元信息 |
| POST | `/api/analyze` | 运行研判（multi / no_causal / single） |
| POST | `/api/approval/start` | 发起 HITL 审批 |
| POST | `/api/approval/{thread_id}/resume` | 批准/拒绝并恢复 |
| GET | `/api/runs` | 最近研判记录 |
| GET | `/api/runs/{run_id}` | 单次研判详情 |

```bash
curl -s -X POST http://localhost:8000/api/analyze \
  -H 'content-type: application/json' \
  -d '{"case_id":"case_001","mode":"multi"}'
```

详见 `docs/api.md`。

## Docker 与 CI

```bash
docker compose up --build      # API on :8000
```

- `Dockerfile`：API 镜像（含 psycopg）
- `Dockerfile.ui`：Streamlit 镜像
- `docker-compose.yml`：Postgres + API + UI
- `.github/workflows/ci.yml`：ruff + pytest
- 持久化：默认 SQLite，`DATABASE_URL` 可切 Postgres；`runs` 与 `approvals` 两张表

## 评测结果

### 真实数据：RCAEval RE2-OB 40 条（metrics + logs）

| mode | R@1 | 95% CI | R@3 | MRR | Fault | Avg ms |
|---|---|---|---|---|---|---|
| **multi**（三源 + 因果） | **70.00%** | [0.55, 0.82] | **82.50%** | **0.75** | 50% | 754 |
| single（仅指标） | 70.00% | [0.55, 0.82] | 82.50% | 0.75 | 50% | 266 |
| no_causal（三源 + 加权） | 45.00% | [0.30, 0.60] | 92.50% | 0.65 | 50% | 739 |

- 因果排序相对加权：**+25pp**
- 分故障类型：disk 100%，mem/socket 83%，delay/loss 57%，**cpu 43%**
- 全分辨率结果 70%；每 5 点降采样变体 75%，**不作为主数字**
- 负结果：multi 与 single 持平，当前 logs 没有改变排序
- traces 单条 10MB，未全量下载

### 合成集：12 条生成 case（消融验证）

| mode | R@1 | R@3 |
|---|---|---|
| multi | 100% | 100% |
| single | 66.67% | 100% |
| no_causal | 0% | 100% |

**注意**：合成集故障模式干净，不代表真实难度。真实数字以 40 条 RCAEval 为准。

## 接入 RCAEval 真实数据

```bash
# 从 HuggingFace 逐条下载 40 条 RE2-OB（metrics + logs）
python -m eval.download_hf_cases --limit 40 --convert

# 评测
python -m eval.runner --filter re2ob_ --report eval/report_rcaeval40.json
```

Zip 整包（Zenodo / Figshare）也可以，用 `eval/download_rcaeval.py`。详见 `docs/rcaeval.md`。

## 目录

```
app/
├── state.py                 # Evidence / Hypothesis / CaseState（含 usage reducer）
├── registry.py              # ToolRegistry
├── graph.py                 # 编排（multi / single / no_causal / multi_llm）
├── runtime.py               # SqliteSaver 持久化
├── hitl.py                  # interrupt / resume 审批图
├── analysis/causal.py       # 因果排序
├── agents/
│   ├── supervisor.py
│   ├── experts.py           # 规则版 metrics / logs / traces
│   ├── llm_experts.py       # LLM 抽取（JSON + Pydantic + 回退）
│   ├── critic.py
│   ├── analyst.py
│   └── reporter.py
├── guardrails/injection.py  # 日志注入检测
├── governance/              # 预算、循环检测
├── providers/               # DeepSeek / Fake，含 token 与成本
└── tools/mock_sources.py    # 三源 mock 工具
data/cases/                  # 58 条（18 合成/样例 + 40 条 RCAEval RE2-OB）
data/rcaeval_fixture/        # RCAEval 格式的最小样例
eval/                        # 生成器 / runner / adapter / bootstrap
tests/                       # 56 个测试
ui/app.py                    # Streamlit
Dockerfile / docker-compose.yml
.github/workflows/ci.yml     # ruff + pytest
docs/                        # 架构、API、评测、RCAEval、简历 bullet
```

---

## 完整版清单

- [x] 多 Agent 编排（Supervisor + 三专家 + Critic + Analyst + Reporter）
- [x] 因果排序 + victim bias 消除
- [x] LLM 结构化抽取 + Schema 校验 + 失败回退
- [x] LLM token / 成本统计
- [x] Checkpoint 持久化 + HITL 中断/恢复
- [x] 注入防护 + 预算 + 循环检测
- [x] 三组消融 + Bootstrap 95% CI
- [x] RCAEval 适配器 + 最小样例
- [x] Streamlit UI
- [x] FastAPI 服务层（analyze / cases / approval / runs）
- [x] 真实遥测客户端（Prometheus / Loki / Tempo）
- [x] Postgres/SQLite 持久化（runs + approvals）
- [x] Streamlit 改走 HTTP API
- [x] Dockerfile / Dockerfile.ui / docker compose
- [x] GitHub Actions CI（ruff + pytest）
- [x] RCAEval 真实样本接入（1 条，checkoutservice CPU 正确诊断）
- [ ] 真实 RCAEval 40 条数据（需下载，代码已就绪）
- [ ] 演示视频（需自己录）

---

## 限制

- 默认专家是规则版；LLM 专家需要 API Key，且输出质量依赖模型。
- 评测集是合成数据，真实数据上指标会明显下降。
- 默认仍用 mock 工具；真实遥测需要配置 `PROMETHEUS_URL` / `LOKI_URL` / `TEMPO_URL`。
- 实时 case 没有 ground truth，不能用于准确率评测。
- HITL 是演示级，没有真实执行器。
- API 没有鉴权、限流、租户隔离。
