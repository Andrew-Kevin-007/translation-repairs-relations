"""Scoring runner: parsed results -> metrics -> GRR -> CIs (day 4 wiring).

HARD GATE (pre-registration discipline): refuses to run unless the frozen
pre-registration commit 61f1ee1 is an ancestor of HEAD — the methods section
cites that ordering. Enforced against git itself, not convention.

Reads a run_matrix parsed-results JSONL + the dataset it ran on, computes per
(model, view, lang): direct/pivot/english F1, GRR with the pre-registered
8-point exclusion, and a paired-bootstrap 95% CI on GRR (pivot/direct paired
on items; English ceiling resampled independently — bootstrap.py). Sign test
requires all 8 study languages; reported n/a otherwise. Holm-Bonferroni is
applied at the decision-table stage (analysis notebook, day 15+), not here.

Unresolved canonicalization slots (model answered NONE / unparseable) are
scored as the placeholder "∅" — they count as wrong predictions, never dropped.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import defaultdict
from pathlib import Path

from bootstrap import hierarchical_bootstrap, percentile_ci, sign_test_consistency
from dataset import load_items
from metrics import Triple, corpus_f1, gap_recovery_ratio, item_counts

PREREG_COMMIT = "61f1ee1"
VIEWS = ("triple", "relation", "entity")
PLACEHOLDER = "∅"


def assert_prereg_ancestry() -> None:
    repo = Path(__file__).resolve().parent.parent
    r = subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor",
                        PREREG_COMMIT, "HEAD"], capture_output=True)
    if r.returncode != 0:
        raise SystemExit(
            "REFUSING TO SCORE: pre-registration commit %s is not an ancestor "
            "of HEAD. See PREREGISTRATION.md / run_matrix.py docstring."
            % PREREG_COMMIT)


def predicted_triples(record: dict) -> list[Triple]:
    out = []
    for c in record["canonical"]:
        out.append(Triple(c["subject_qid"] or PLACEHOLDER,
                          c["property_pid"] or PLACEHOLDER,
                          (c["object"] if c["object"] not in (None, "") else PLACEHOLDER)))
    return out


def collect_counts(results_path: str | Path, dataset_path: str | Path):
    """-> counts[(model, arm, lang)] = list of per-item metric-count dicts,
    ordered by item id so paired arms share indexing."""
    gold = {it.id: it for it in load_items(dataset_path)}
    by_cell = defaultdict(dict)  # (model, arm, lang) -> {item_id: counts}
    for line in Path(results_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        item = gold[r["item_id"]]
        counts = item_counts(predicted_triples(r), item.gold_triples())
        by_cell[(r["model"], r["arm"], r["lang"])][r["item_id"]] = counts
    ordered = {}
    for cell, per_item in by_cell.items():
        ordered[cell] = [per_item[k] for k in sorted(per_item)]
    return ordered


def score(results_path, dataset_path, n_resamples: int | None = None):
    assert_prereg_ancestry()
    cells = collect_counts(results_path, dataset_path)
    models = sorted({m for (m, _, _) in cells})
    langs = sorted({l for (_, a, l) in cells if a in ("direct", "pivot")})
    report = {"cells": {}, "grr": {}}

    for model in models:
        eng = cells.get((model, "english", "en"), [])
        for view in VIEWS:
            m_eng = corpus_f1(eng, view) if eng else None
            directions = []
            for lang in langs:
                d = cells.get((model, "direct", lang), [])
                p = cells.get((model, "pivot", lang), [])
                if not d or not p or m_eng is None:
                    continue
                m_d, m_p = corpus_f1(d, view), corpus_f1(p, view)
                grr = gap_recovery_ratio(m_p, m_d, m_eng)
                key = "%s/%s/%s" % (model, view, lang)
                report["cells"][key] = {"direct": m_d, "pivot": m_p,
                                        "english": m_eng, "grr": grr}
                if grr is None:
                    continue  # pre-registered exclusion: baseline gap < 8 pts
                directions.append(1 if (m_p - m_d) > 0 else -1)
                groups = {"direct": d, "pivot": p, "english": eng}

                def stat(res, _view=view):
                    g = gap_recovery_ratio(corpus_f1(res["pivot"], _view),
                                           corpus_f1(res["direct"], _view),
                                           corpus_f1(res["english"], _view))
                    return g if g is not None else float("nan")

                kw = {"n_resamples": n_resamples} if n_resamples else {}
                samples = hierarchical_bootstrap(
                    groups, stat, paired_groups=[("direct", "pivot")], **kw)
                clean = [s for s in samples if s == s]  # drop NaN (excluded draws)
                report["grr"][key] = {
                    "grr": grr,
                    "ci95": percentile_ci(clean) if clean else None,
                    "resamples_used": len(clean),
                }
            report["grr"]["%s/%s/_signtest" % (model, view)] = (
                sign_test_consistency(directions) if len(directions) == 8
                else "n/a (%d languages)" % len(directions))
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--resamples", type=int, default=None,
                    help="override N_RESAMPLES (testing only; runs use 10k)")
    args = ap.parse_args()
    report = score(args.results, args.dataset, args.resamples)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print("report ->", args.out)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
