"""Closed relation inventory for stage-2 canonicalization (canonicalize.py §5).

Reads the predicate_map.json emitted by gold_canonicalize.py (label -> PID,
exact-match verified) and materializes the [{id, label, description}] list the
run matrix passes as --property-inventory. Descriptions come from the same
cached Wikidata search layer, so the archive stays self-contained.

Usage (from src/):
  python build_inventory.py --map D:/xlkg-data/gold/predicate_map.json \
      --out D:/xlkg-data/gold/property_inventory.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from wikidata_client import WikidataClient


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    pred_map = json.loads(Path(args.map).read_text(encoding="utf-8"))
    wd = WikidataClient()
    inventory = []
    for label, rec in sorted(pred_map.items()):
        pid = rec.get("pid")
        if not pid:
            continue
        desc = ""
        for h in wd.search_entities(label, lang="en", limit=5,
                                    entity_type="property"):
            if h.get("id") == pid:
                desc = h.get("description", "")
                break
        inventory.append({"id": pid, "label": rec.get("wd_label") or label,
                          "description": desc})
    # one entry per PID even if several gold labels map to it
    seen, unique = set(), []
    for e in inventory:
        if e["id"] in seen:
            continue
        seen.add(e["id"])
        unique.append(e)
    Path(args.out).write_text(json.dumps(unique, indent=2, ensure_ascii=False),
                              encoding="utf-8")
    print("inventory: %d properties -> %s" % (len(unique), args.out))


if __name__ == "__main__":
    main()
