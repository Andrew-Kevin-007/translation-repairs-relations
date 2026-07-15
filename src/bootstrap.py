"""Hierarchical/paired bootstrap per PREREGISTRATION.md section 5.

Pairing structure:
  - pivot vs direct: item-paired (same input items) -> resample item indices once,
    apply to both arms.
  - English ceiling: different items (unpaired) -> independent resampling.
    (See the English-ceiling pairing note, PREREGISTRATION.md section 3.)

All CIs: percentile, 95%, N_RESAMPLES = 10_000 (pre-registered).
"""

from __future__ import annotations

import random
from typing import Callable, Sequence

N_RESAMPLES = 10_000
CI_LEVEL = 0.95


def percentile_ci(samples: list[float], level: float = CI_LEVEL) -> tuple[float, float]:
    s = sorted(samples)
    lo = s[int((1 - level) / 2 * (len(s) - 1))]
    hi = s[int((1 + level) / 2 * (len(s) - 1))]
    return lo, hi


def paired_bootstrap(
    counts_a: Sequence,
    counts_b: Sequence,
    stat: Callable[[Sequence, Sequence], float],
    n_resamples: int = N_RESAMPLES,
    seed: int = 20260715,
) -> list[float]:
    """Item-paired resampling: one index draw applied to both arms.
    counts_a[i] and counts_b[i] must refer to the same input item."""
    assert len(counts_a) == len(counts_b), "paired arms must share item indexing"
    rng = random.Random(seed)
    n = len(counts_a)
    out = []
    for _ in range(n_resamples):
        idx = [rng.randrange(n) for _ in range(n)]
        out.append(stat([counts_a[i] for i in idx], [counts_b[i] for i in idx]))
    return out


def hierarchical_bootstrap(
    grouped_counts: dict[str, Sequence],
    stat: Callable[[dict[str, Sequence]], float],
    paired_groups: Sequence[Sequence[str]] = (),
    n_resamples: int = N_RESAMPLES,
    seed: int = 20260715,
) -> list[float]:
    """Groups listed together in paired_groups share one index draw (paired);
    all other groups are resampled independently (e.g. the English ceiling)."""
    rng = random.Random(seed)
    pair_of = {}
    for cluster in paired_groups:
        for g in cluster:
            pair_of[g] = tuple(cluster)
    out = []
    for _ in range(n_resamples):
        draws: dict[tuple, list[int]] = {}
        resampled = {}
        for g, counts in grouped_counts.items():
            n = len(counts)
            key = pair_of.get(g, (g,))
            if key not in draws:
                draws[key] = [rng.randrange(n) for _ in range(n)]
            resampled[g] = [counts[i] for i in draws[key]]
        out.append(stat(resampled))
    return out


def sign_test_consistency(directions: Sequence[int]) -> bool:
    """Pre-registered cross-language consistency: >=7 of 8 languages in the same
    direction (exact two-sided binomial at n=8: P(>=7) = 9/256 * 2 ~= 0.070 one-sided
    0.035, two-sided 0.070 -- the pre-registration fixes the >=7/8 count rule itself)."""
    pos = sum(1 for d in directions if d > 0)
    neg = sum(1 for d in directions if d < 0)
    return max(pos, neg) >= 7 and len(directions) == 8


def holm_bonferroni(pvals: dict[str, float], alpha: float = 0.05) -> dict[str, bool]:
    """Holm-Bonferroni over the 6 primary-family tests (2 metrics x 3 systems)."""
    ordered = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(ordered)
    rejected = {}
    still_rejecting = True
    for i, (name, p) in enumerate(ordered):
        if still_rejecting and p <= alpha / (m - i):
            rejected[name] = True
        else:
            still_rejecting = False
            rejected[name] = False
    return rejected
