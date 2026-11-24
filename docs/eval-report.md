# Evaluation Report

> 数据分两部分：**RCAEval RE2-OB 40 条真实 case**（metrics + logs）和 **12 条合成 case**（消融与链路验证）。所有数字可复现。

## 1. 真实数据：RCAEval RE2-OB 40 条

数据：从 HuggingFace 逐条下载，按 fault type 分层抽样，Online Boutique 拓扑，metrics + logs；traces 单条约 10MB，未全量下载。

| mode | R@1 | 95% CI | R@3 | MRR | Fault Accuracy | Avg Latency |
|---|---|---|---|---|---|---|
| **multi**（三源 + 因果） | **70.00%** | [0.55, 0.82] | **82.50%** | **0.75** | 50.00% | 754.6ms |
| single（仅指标） | 70.00% | [0.55, 0.82] | 82.50% | 0.75 | 50.00% | 265.6ms |
| no_causal（三源 + 加权） | 45.00% | [0.30, 0.60] | 92.50% | 0.65 | 50.00% | 738.9ms |

### 分故障类型（multi）

| fault | R@1 |
|---|---|
| disk | 7/7 = 100% |
| mem | 5/6 = 83% |
| socket | 5/6 = 83% |
| delay | 4/7 = 57% |
| loss | 4/7 = 57% |
| cpu | 3/7 = 43% |

### 结论

1. **因果排序有效**：相对加权排序 R@1 +25pp（70% vs 45%）。
2. **多源未带来增益**：multi 与 single 持平，说明当前 logs 证据没有改变排序；这是负结果，不粉饰。
3. **R@3 82.5%**：7 条真实根因不在 Top-3，集中在 currencyservice cpu 与 checkoutservice delay。
4. **cpu 是弱项**：43%；delay/loss 57%，需要更好的变点检测或 traces。
5. **故障类型三分类只有 50%**：cpu/mem/disk 与 delay/loss/socket 在遥测上区分度低，下一步按原始 fault type 细分。

## 2. 合成集：12 条生成 case

用于消融与链路验证，故障模式干净，不代表真实难度。

| mode | R@1 | 95% CI | R@3 | MRR |
|---|---|---|---|---|
| multi | 100.00% | [1.00, 1.00] | 100% | 1.00 |
| single | 66.67% | [0.42, 0.92] | 100% | 0.83 |
| no_causal | 0.00% | [0.00, 0.00] | 100% | 0.50 |

合成集刻意制造 victim bias，所以 `no_causal` 全错；它验证的是"因果惩罚"机制，不是真实性能。

## 3. 复现

```bash
# 真实 40 条
python -m eval.download_hf_cases --limit 40 --convert
python -m eval.runner --filter re2ob_ --report eval/report_rcaeval40.json

# 合成 12 条
python -m eval.generate_cases
python -m eval.runner --filter gen_ --report eval/report_synthetic.json
```

## 4. 口径

- R@k：按 case 统计，真值是否在 Top-k。
- MRR：第一个正确候选排名的倒数。
- 95% CI：1000 次 Bootstrap，2.5% / 97.5% 分位。
- 延迟：单 case 端到端；规则版，无 LLM 网络开销。

## 5. 限制

- 40 条只覆盖 RE2-OB 一个系统；不代表 Sock Shop / Train Ticket。
- traces 未全量下载，multi 实际是 metrics + logs。
- 故障类型三分类过粗，50% 不作为卖点。
- 合成集不能用于宣称生产准确率。

> 采样敏感性：全分辨率 70%；每 5 点降采样到 12MB 仓库后为 75%。主数字取全分辨率 70%，避免被质疑按结果调采样。
