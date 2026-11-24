# RCAEval 接入

## 1. 数据

- 仓库：https://github.com/phamquiluan/RCAEval
- 数据：Zenodo / HuggingFace（RE1 / RE2 / RE3，约 5GB，按需下子集）
- 优先用 **RE2 / RE3**（含 logs.csv、traces.csv），RE1 只有指标

每个 case 目录大致长这样：

```
case_x/
├── metrics.json
├── logs.csv
├── traces.csv
├── inject_time.txt
└── ground_truth.json   # 本项目要求；可从官方标注整理
```

`ground_truth.json` 示例：

```json
{
  "case_id": "re_case_a",
  "alert_service": "checkout",
  "root_cause_service": "payment",
  "fault_type": "dependency_timeout",
  "topology": {"checkout": ["payment"]}
}
```

## 2. 下载（推荐 HuggingFace 逐条）

```bash
python -m eval.download_hf_cases --limit 40 --convert
```

只下载 40 条 metrics+logs，约 20MB；不会拉 3.4GB 全量。

也可以下载整包：



```bash
python -m eval.download_rcaeval --sample   # 12MB 官方多源样本
```

或指定 zip：

```bash
python -m eval.download_rcaeval \
  --url "https://zenodo.org/records/14590730/files/RE2-OB.zip?download=1"
```

## 3. 转换

```bash
python -m eval.rcaeval_adapter \
  --root /path/to/RCAEval \
  --out data/cases \
  --limit 40
```

转换器支持：

- `metrics.json`：`{service: [points]}` 或 `[{service, ts, p99_ms, error_rate, cpu}]`
- `logs.csv`：`timestamp,service,level,message`
- `traces.csv`：`timestamp,service,p99_ms,error_rate`

## 4. 评测

```bash
python -m eval.runner
```

报告写入 `eval/report.json`，含 R@1 / R@3 / MRR / 95% CI / 成本。

## 5. 注意

- 官方数据的字段名可能与上面不同，先跑 5 条确认映射，再扩到 40 条。
- 没有 `ground_truth.json` 的 case 不会被转换；先补标注。
- 真实数据上 R@1 会明显低于合成集，这是正常的，不要为了好看调参到过拟合。


## 已完成的真实样本验证

`data/cases/re_sample_checkout_cpu.json` 来自官方 `multi-source-data.zip`：

- 真实注入：checkoutservice CPU 从 0.4 飙到 20（约 48 倍）
- 系统输出：根因 checkoutservice，故障类型 resource_saturation
- 证据：metrics z=30.1，traces p99=615ms

这说明 wide `metrics.csv`、真实 `logs.csv`、`traces.csv` 的解析链路是通的。


## 6. 40 条真实结果

| mode | R@1 | R@3 | MRR |
|---|---|---|---|
| multi | 70.00% | 82.50% | 0.75 |
| single | 70.00% | 82.50% | 0.75 |
| no_causal | 45.00% | 92.50% | 0.65 |

分故障类型：disk 100%，mem/socket 83%，delay/loss 57%，cpu 43%。全分辨率 70%；降采样变体 75% 不作为主数字。
