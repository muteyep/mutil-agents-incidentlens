from __future__ import annotations

from eval.stats import bootstrap_ci


def test_bootstrap_all_ones() -> None:
    low, high, mean = bootstrap_ci([1.0] * 20)
    assert low == high == mean == 1.0


def test_bootstrap_bounds_are_ordered() -> None:
    values = [1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 1.0]
    low, high, mean = bootstrap_ci(values)
    assert 0.0 <= low <= mean <= high <= 1.0


def test_bootstrap_empty() -> None:
    assert bootstrap_ci([]) == (0.0, 0.0, 0.0)
