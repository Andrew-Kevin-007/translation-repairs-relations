"""C2 gold-incompleteness analysis (PREREGISTRATION.md secondary claim C2).

Classifies every predicted triple from a parsed-results file three ways
(wikidata_check): IN_GOLD / TRUE_IN_WIKIDATA / CANDIDATE_HALLUCINATION.
C2's pre-registered rule: if >= 5% of not-in-gold predictions are verifiably
TRUE in Wikidata, the paper must report gold incompleteness and its effect on
precision estimates.

Only fully-resolved predictions (QID subject + PID) are classifiable against
Wikidata; unresolved ones are counted separately as 'unresolved' (they are
already penalized by the primary metrics; they are not hallucination evidence).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from dataset import load_items
from wikidata_check import TripleClass, classify_triple
from wikidata_client import WikidataClient
from metrics import Triple


def analyze(results_path, dataset_path, client: WikidataClient | None = None):
    client = client or WikidataClient()
    gold = {it.id: it.gold_triples() for it in load_items(dataset_path)}
    per_cell: dict[tuple, Counter] = {}
    for line in Path(results_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        cell = (r["model"], r["arm"], r["lang"])
        c = per_cell.setdefault(cell, Counter())
        for p in r["canonical"]:
            if not p["subject_qid"] or not p["property_pid"] or p["object"] in (None, ""):
                c["unresolved"] += 1
                continue
            t = Triple(p["subject_qid"], p["property_pid"], str(p["object"]))
            c[classify_triple(t, gold[r["item_id"]], client).value] += 1
    report = {}
    for cell, c in sorted(per_cell.items()):
        not_in_gold = c[TripleClass.TRUE_IN_WIKIDATA.value] + \
            c[TripleClass.CANDIDATE_HALLUCINATION.value]
        share = (c[TripleClass.TRUE_IN_WIKIDATA.value] / not_in_gold
                 if not_in_gold else None)
        report["%s/%s/%s" % cell] = {
            **{k: c[k] for k in sorted(c)},
            "true_share_of_not_in_gold": share,
            "c2_trigger_5pct": (share is not None and share >= 0.05),
        }
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--dataset", required=True)
    args = ap.parse_args()
    print(json.dumps(analyze(args.results, args.dataset), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
