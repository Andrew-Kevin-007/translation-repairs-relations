"""Component metrics for KG-population evaluation.

Pre-registered decomposition (PREREGISTRATION.md section 2):
  - relation_f1:  property correct, entities ignored
  - entity_f1:    subject/object QIDs correct, property ignored
  - triple_f1:    exact (subject, property, object) match

Strict variant matches Wikidata IDs (QIDs / PIDs); relaxed variant matches
normalized surface strings. Gold and predictions are per-item lists of triples.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Triple:
    subject: str   # QID (strict) or surface form (relaxed)
    property: str  # PID (strict) or normalized label (relaxed)
    obj: str       # QID / literal (strict) or surface form (relaxed)


def normalize_surface(s: str) -> str:
    """Unicode-normalize and casefold a surface form for relaxed matching."""
    return unicodedata.normalize("NFKC", s).casefold().strip()


def _prf(tp: int, n_pred: int, n_gold: int) -> tuple[float, float, float]:
    p = tp / n_pred if n_pred else 0.0
    r = tp / n_gold if n_gold else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f


def _match_count(pred: Iterable, gold: Iterable) -> int:
    """Multiset intersection size (each gold element consumed at most once)."""
    gold_pool = list(gold)
    tp = 0
    for x in pred:
        if x in gold_pool:
            gold_pool.remove(x)
            tp += 1
    return tp


def item_counts(pred: list[Triple], gold: list[Triple]) -> dict[str, tuple[int, int, int]]:
    """Per-item (tp, n_pred, n_gold) for each metric — the unit the bootstrap resamples."""
    views = {
        "triple": lambda t: (t.subject, t.property, t.obj),
        "relation": lambda t: t.property,
        "entity": lambda t: (t.subject, t.obj),
    }
    out = {}
    for name, view in views.items():
        p = [view(t) for t in pred]
        g = [view(t) for t in gold]
        out[name] = (_match_count(p, g), len(p), len(g))
    return out


def corpus_f1(counts: list[dict[str, tuple[int, int, int]]], metric: str) -> float:
    """Micro-averaged F1 over per-item counts (as resampled by the bootstrap)."""
    tp = sum(c[metric][0] for c in counts)
    n_pred = sum(c[metric][1] for c in counts)
    n_gold = sum(c[metric][2] for c in counts)
    return _prf(tp, n_pred, n_gold)[2]


def gap_recovery_ratio(m_pivot: float, m_direct: float, m_english: float) -> float | None:
    """GRR_m per PREREGISTRATION.md section 3. Returns None for excluded cells
    (baseline gap < 8 F1 points, on the 0-100 scale)."""
    baseline_gap = m_english - m_direct
    if baseline_gap * 100 < 8:
        return None  # underpowered cell — logged and reported, no verdict
    return (m_pivot - m_direct) / baseline_gap
