"""Assemble the run-matrix inputs once all per-language gold files exist.

Steps (idempotent, safe to rerun):
  1. Merge every predicate_map*.json fragment in the gold dir; for languages
     whose fragment is missing (produced before per-language filenames), the
     distinct predicate labels are re-resolved from the XAlign source — every
     lookup replays from the shared cache, so this costs no new network.
     Conflicting label->PID mappings abort loudly (should be impossible).
  2. Build property_inventory.json ([{id,label,description}]) from the merged
     map via the cached property search (same as build_inventory.py).
  3. Concatenate all <lang>_test.jsonl gold files into all_test.jsonl (the
     single dataset file run_matrix.py consumes) and print per-language and
     total counts plus a stats roll-up for the paper's Table 1.

Usage (from src/):
  python prepare_matrix.py --xalign D:/xlkg-data/xalign/v2.0 \
      --gold D:/xlkg-data/gold --langs hi,bn,te,ta,kn,ml,mr,gu,en
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from gold_canonicalize import GoldCanonicalizer
from wikidata_client import WikidataClient

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xalign", required=True)
    ap.add_argument("--gold", required=True)
    ap.add_argument("--langs", required=True)
    args = ap.parse_args()
    gold = Path(args.gold)
    langs = [l.strip() for l in args.langs.split(",") if l.strip()]

    # ---- 1. merge predicate maps -------------------------------------------
    merged: dict[str, dict] = {}
    covered: set[str] = set()
    for frag in sorted(gold.glob("predicate_map*.json")):
        data = json.loads(frag.read_text(encoding="utf-8"))
        stem = frag.stem  # predicate_map.<langs> or plain predicate_map
        if "." in stem:
            covered.update(stem.split(".", 1)[1].split("-"))
        for label, rec in data.items():
            if label in merged and merged[label]["pid"] != rec["pid"]:
                raise SystemExit("CONFLICT for %r: %s vs %s"
                                 % (label, merged[label]["pid"], rec["pid"]))
            merged.setdefault(label, rec)

    missing = [l for l in langs if l not in covered]
    if missing:
        canon = GoldCanonicalizer(WikidataClient())
        for lang in missing:
            src = Path(args.xalign) / lang / "test.jsonl"
            labels = set()
            for ln in src.read_text(encoding="utf-8").splitlines():
                if ln.strip():
                    for f in json.loads(ln).get("facts") or []:
                        labels.add(f["predicate"])
            for label in sorted(labels):
                canon.predicate_pid(label)          # cache-hot resolution
        for label, rec in canon.pred.items():
            if label in merged and merged[label]["pid"] != rec["pid"]:
                raise SystemExit("CONFLICT for %r (regen): %s vs %s"
                                 % (label, merged[label]["pid"], rec["pid"]))
            merged.setdefault(label, rec)
        print("regenerated predicate labels for: %s" % ",".join(missing))

    out_map = gold / "predicate_map.merged.json"
    out_map.write_text(json.dumps(dict(sorted(merged.items())), indent=2,
                                  ensure_ascii=False), encoding="utf-8")
    flagged = {l: r for l, r in merged.items() if r["match"] != "exact"}
    print("predicates merged: %d (%d flagged non-exact)" % (len(merged), len(flagged)))
    for l, r in flagged.items():
        print("  REVIEW: %r -> %s (%s)" % (l, r["pid"], r["match"]))

    # ---- 2. property inventory ---------------------------------------------
    wd = WikidataClient()
    inventory, seen = [], set()
    for label, rec in sorted(merged.items()):
        pid = rec.get("pid")
        if not pid or pid in seen:
            continue
        seen.add(pid)
        desc = ""
        for h in wd.search_entities(label, lang="en", limit=5,
                                    entity_type="property"):
            if h.get("id") == pid:
                desc = h.get("description", "")
                break
        inventory.append({"id": pid, "label": rec.get("wd_label") or label,
                          "description": desc})
    inv_path = gold / "property_inventory.json"
    inv_path.write_text(json.dumps(inventory, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print("inventory: %d properties -> %s" % (len(inventory), inv_path))

    # ---- 3. combined dataset + Table-1 roll-up -----------------------------
    combined = gold / "all_test.jsonl"
    total = 0
    with open(combined, "w", encoding="utf-8") as out:
        for lang in langs:
            f = gold / ("%s_test.jsonl" % lang)
            n = 0
            for ln in f.read_text(encoding="utf-8").splitlines():
                if ln.strip():
                    out.write(ln + "\n")
                    n += 1
            total += n
            stats = json.loads((gold / ("%s_stats.json" % lang))
                               .read_text(encoding="utf-8"))
            print("%-3s kept %4d / %4d  (%.1f%%)  drops=%s"
                  % (lang, stats["kept"], stats["source_items"],
                     stats["kept_pct"], stats["drops"]))
    print("dataset: %d items -> %s" % (total, combined))


if __name__ == "__main__":
    main()
