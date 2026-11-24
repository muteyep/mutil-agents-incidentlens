# HTTP API

## 启动

```bash
uvicorn app.api.app:app --reload --port 8000
```

打开 http://localhost:8000/docs 查看 Swagger。

## 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 健康检查 |
| GET | `/api/cases` | case 列表 |
| GET | `/api/cases/{case_id}` | 单条 case 元信息 |
| POST | `/api/analyze` | 运行多 Agent 研判 |
| POST | `/api/approval/start` | 发起高风险动作审批，返回 `thread_id` |
| POST | `/api/approval/{thread_id}/resume` | 批准/拒绝并恢复 |
| GET | `/api/runs` | 最近研判记录 |
| GET | `/api/runs/{run_id}` | 单次研判详情 |

## 研判示例

```bash
curl -s -X POST http://localhost:8000/api/analyze \
  -H 'content-type: application/json' \
  -d '{"case_id":"case_001","mode":"multi"}' | python -m json.tool
```

返回：

```json
{
  "case_id": "case_001",
  "report": "# 告警研判报告 ...",
  "critique": "causal ranking: payment=0.82 ...",
  "evidences": [{"source": "metrics", "service": "payment", "severity": 1.0}],
  "hypotheses": [{"service": "payment", "fault_type": "dependency_timeout", "confidence": 0.58}],
  "usage": {},
  "latency_ms": 5.2
}
```

## HITL 示例

```bash
# 1) 发起审批，图会挂起
curl -s -X POST http://localhost:8000/api/approval/start \
  -H 'content-type: application/json' \
  -d '{"action":"restart payment","risk":"high"}'

# 2) 用返回的 thread_id 恢复
curl -s -X POST http://localhost:8000/api/approval/<thread_id>/resume \
  -H 'content-type: application/json' \
  -d '{"approved":true}'
```

## 模式

`/api/analyze` 的 `mode` 支持：

- `multi`：三源 + 因果（默认）
- `no_causal`：三源 + 加权（消融）
- `single`：仅指标（baseline）

`use_llm=true` 时需要 `DEEPSEEK_API_KEY`，否则回退规则版。

## 限制

- 审批图状态使用 `MemorySaver`，进程重启后丢失；审批**记录**已写数据库（`approvals` 表），但图状态没有持久化。
- 研判记录写入 `runs` 表，默认 SQLite（`DATABASE_URL` 可切 Postgres）。
- 没有鉴权、租户隔离、限流；这是演示服务，不是生产网关。
