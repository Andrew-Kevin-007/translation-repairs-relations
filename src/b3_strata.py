"""B3 popularity stratification (PREREGISTRATION.md decision-table row 6).

Row-6 criterion, licensed only by this module's outputs:
  (i)  bottom-vs-top popularity-quartile error ratio >= 1.5 within the PIVOT arm
  (ii) excluding bottom-quartile entities shrinks the residual pivot-vs-English
       gap by >= 50%

Implementation choices fixed BEFORE data (freeze day 8 with the rest):
  - popularity = Wikidata sitelink count of the GOLD entity
    (wikidata_client.sitelink_count; snapshot window reported);
  - quartiles computed over the deduplicated gold-entity inventory of the
    study slice (per language set, not per item);
  - an "occurrence" = one gold subject-or-object QID in one item; the
    occurrence is an ERROR if that QID does not appear in the model's
    predicted entities for the item (either slot — recovery, not position);
  - "excluding bottom-quartile entities" (criterion ii) = dropping gold
    triples whose subject OR object is bottom-quartile from BOTH arms'
    counts, then recomputing the pivot-vs-English entity-F1 gap.
"""

from __future__ import annotations

from collections import defaultdict


def assign_quartiles(sitelinks: dict[str, int]) -> dict[str, int]:
    """QID -> quartile 1 (bottom) .. 4 (top), by sitelink count over the gold
    inventory. Ties broken by QID sort for determinism; quartile edges by rank."""
    ranked = sorted(sitelinks, key=lambda q: (sitelinks[q], q))
    n = len(ranked)
    out = {}
    for i, qid in enumerate(ranked):
        out[qid] = min(4, 1 + (i * 4) // n) if n else 1
    return out


def occurrence_errors(records: list[dict], gold_of: dict[str, list[dict]],
                      quartile_of: dict[str, int]):
    """-> per-quartile [errors, occurrences] over parsed-result records
    (one arm's records). gold_of: item_id -> gold triple dicts."""
    stats = defaultdict(lambda: [0, 0])
    for r in records:
        predicted = set()
        for c in r["canonical"]:
            predicted.add(c["subject_qid"])
            predicted.add(c["object"])
        for g in gold_of[r["item_id"]]:
            for qid in (g["subject_qid"], str(g["object"])):
                if qid not in quartile_of:
                    continue  # literals / entities without sitelink data
                q = quartile_of[qid]
                stats[q][1] += 1
                if qid not in predicted:
                    stats[q][0] += 1
    return dict(stats)


def error_ratio(stats: dict[int, list[int]]) -> float | None:
    """Bottom(1) vs top(4) occurrence error-rate ratio. None if either
    quartile has no occurrences or top has zero errors and bottom doesn't
    (reported as inf by caller policy — here None signals 'not computable')."""
    b = stats.get(1)
    t = stats.get(4)
    if not b or not t or b[1] == 0 or t[1] == 0:
        return None
    rb = b[0] / b[1]
    rt = t[0] / t[1]
    if rt == 0:
        return float("inf") if rb > 0 else None
    return rb / rt


def gap_shrinkage(gap_full: float, gap_excluded: float) -> float | None:
    """Fractional shrinkage of the residual pivot-vs-English gap when
    bottom-quartile entities are excluded. gap = m_english - m_pivot (>=0
    expected); shrinkage = 1 - gap_excluded/gap_full."""
    if gap_full <= 0:
        return None  # no residual gap to shrink — row 6 (ii) not applicable
    return 1.0 - (gap_excluded / gap_full)


if __name__ == "__main__":
    # deterministic self-check, no network
    sl = {"Q1": 2, "Q2": 5, "Q3": 40, "Q4": 300, "Q5": 3, "Q6": 8, "Q7": 90, "Q8": 700}
    q = assign_quartiles(sl)
    assert q["Q1"] == 1 and q["Q8"] == 4, q
    recs = [{"item_id": "i1", "canonical": [{"subject_qid": "Q8", "object": "Q3"}]}]
    gold = {"i1": [{"subject_qid": "Q8", "object": "Q1"}]}
    st = occurrence_errors(recs, gold, q)
    assert st[4] == [0, 1] and st[1] == [1, 1], st
    assert error_ratio({1: [2, 4], 4: [1, 4]}) == 2.0
    assert abs(gap_shrinkage(0.10, 0.04) - 0.6) < 1e-12
    assert gap_shrinkage(0.0, 0.0) is None
    print("b3_strata self-check OK")
