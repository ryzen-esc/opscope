"""Small stats helpers shared by every insight: sample-size text and Wilson intervals."""
from __future__ import annotations

import math

MIN_SAMPLE = 8  # hide percentage claims below this many trials


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for k successes out of n."""
    if n == 0:
        return 0.0, 0.0
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def pct(k: int, n: int) -> float:
    return k / n if n else 0.0


def of(k: int, n: int, unit: str = "rounds") -> str:
    """'48 of 64 rounds' — the sample-size badge every insight carries."""
    return f"{k} of {n} {unit}"
