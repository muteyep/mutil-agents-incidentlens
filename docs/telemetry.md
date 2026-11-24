# 真实遥测接入

## 环境变量

```bash
export PROMETHEUS_URL=http://localhost:9090
export LOKI_URL=http://localhost:3100
export TEMPO_URL=http://localhost:3200
```

## 运行

```bash
python -m app.telemetry.live \
  --service checkout \
  --services checkout,payment,redis \
  --window 15
```

流程：

```
Prometheus query_range  → 指标点（p99/error/cpu）
Loki query_range        → 日志（level/message）
Tempo /api/search       → span 摘要（p99/error）
        ↓
build_live_case() → 注册为内存 case → 复用多 Agent 图
```

## 指标假设

默认 PromQL 使用 OpenTelemetry Demo 的命名：

| 维度 | 默认指标 |
|---|---|
| 延迟 | `histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[1m]))` |
| 错误率 | `rate(http_requests_total{status=~"5.."}) / rate(http_requests_total)` |
| CPU | `rate(container_cpu_usage_seconds_total[1m])` |

指标名可以改 `PrometheusClient(...)` 的构造参数。不同公司命名不同，**不要假设你的环境一致**。

## 限制

- `build_live_case` 的 `ground_truth` 是 `unknown`，因为线上没有真值；它用于演示"接实时数据"，不用于算准确率。
- Tempo search 只给 duration，错误率暂设为 0；要做准确错误率需要逐个 trace 查询 span。
- 没有鉴权、租户隔离、采样控制；生产要在网关层补。
