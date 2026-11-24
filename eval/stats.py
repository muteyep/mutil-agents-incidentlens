from __future__ import annotations

import random


def bootstrap_ci(
    values: list[float],
    *,
    n: int = 1000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Return (low, high, mean) for the bootstrap distribution of the mean."""
    if not values:
        return (0.0, 0.0, 0.0)
    rng = random.Random(seed)
    means: list[float] = []
    size = len(values)
    for _ in range(n):
        sample = [values[rng.randrange(size)] for _ in range(size)]
        means.append(sum(sample) / size)
    means.sort()
    low = means[int(alpha / 2 * n)]
    high = means[min(n - 1, int((1 - alpha / 2) * n) - 1)]
    return (round(low, 4), round(high, 4), round(sum(values) / size, 4))
