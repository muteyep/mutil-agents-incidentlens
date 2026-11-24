from __future__ import annotations

from eval.runner import run_mode, summarize


def test_multi_beats_single_baseline() -> None:
    multi = summarize(run_mode("multi", filter_prefix="gen_"))
    single = summarize(run_mode("single", filter_prefix="gen_"))
    assert multi["r_at_1"] >= 0.9
    assert multi["r_at_1"] > single["r_at_1"]


def test_causal_beats_weighted_on_victim_bias() -> None:
    multi = summarize(run_mode("multi", filter_prefix="gen_"))
    no_causal = summarize(run_mode("no_causal", filter_prefix="gen_"))
    assert multi["r_at_1"] > no_causal["r_at_1"]
