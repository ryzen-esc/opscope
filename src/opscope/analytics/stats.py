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
    # The bounds are exactly 0 at k == 0 and exactly 1 at k == n; floating point can land a hair off (wilson(0, 44)
    # gave 7e-18), which made surprise() see a gap from a typical rate of 0 that isn't there.
    lo = 0.0 if k == 0 else max(0.0, centre - half)
    hi = 1.0 if k == n else min(1.0, centre + half)
    return lo, hi


def pct(k: int, n: int) -> float:
    return k / n if n else 0.0


TYPICAL_MIN_ROUNDS = 2 * MIN_SAMPLE  # a team needs this many rounds to count toward "the typical team"
TYPICAL_MIN_TEAMS = 4


def typical_rate(k, n, min_rounds: int = TYPICAL_MIN_ROUNDS, min_teams: int = TYPICAL_MIN_TEAMS) -> tuple[float, str]:
    """The comparison rate for a group of teams, robust to one extreme team.

    k, n: per-team successes and trials (array-likes). Returns (rate, method):
    - "typical team": the median of per-team rates over teams with at least `min_rounds` trials, when at least
      `min_teams` qualify. One team that does something constantly can't drag this number up.
    - "all rounds": the pooled rate, when too few teams qualify for a median to mean much.
    """
    import numpy as np
    k, n = np.asarray(k, float), np.asarray(n, float)
    big = n >= min_rounds
    if big.sum() >= min_teams:
        return float(np.median(k[big] / n[big])), "typical team"
    return (float(k.sum() / n.sum()) if n.sum() else 0.0), "all rounds"


def of(k: int, n: int, unit: str = "rounds") -> str:
    """'48 of 64 rounds' — the sample-size badge every insight carries."""
    return f"{k} of {n} {unit}"
