"""Dataset contract for the run matrix.

One JSONL item per evaluation sentence:
  {"id": "...", "lang": "ta",              # study code; "en" = control slice
   "sentence": "...",                       # source-language text
   "gold": [{"subject_qid": "Q1445", "property_pid": "P36", "object": "Q1352"}]}
`object` is a QID or a literal (date/quantity as string).

Both real data (XAlign reversed, or the SPARQL-rebuild fallback) and the
synthetic fixtures (src/fixtures/) are materialized into this one format, so
the whole pipeline downstream of the loader is data-source-agnostic.
Real data lives under data/ (gitignored); fixtures are committed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from metrics import Triple

REQUIRED = ("id", "lang", "sentence", "gold")


@dataclass(frozen=True)
class Item:
    id: str
    lang: str
    sentence: str
    gold: tuple  # of dicts as loaded

    def gold_triples(self) -> list[Triple]:
        return [Triple(g["subject_qid"], g["property_pid"], str(g["object"]))
                for g in self.gold]


def load_items(path: str | Path) -> list[Item]:
    items = []
    seen = set()
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        missing = [k for k in REQUIRED if k not in obj]
        if missing:
            raise ValueError("%s line %d: missing %s" % (path, n, missing))
        if obj["id"] in seen:
            raise ValueError("%s line %d: duplicate id %r" % (path, n, obj["id"]))
        seen.add(obj["id"])
        items.append(Item(obj["id"], obj["lang"], obj["sentence"],
                          tuple(obj["gold"])))
    return items
