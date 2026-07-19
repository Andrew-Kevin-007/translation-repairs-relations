"""Amendment 2 (A5) re-parse: rebuild stage-2 canonical fields from the frozen
raw archives under the completed format-echo leniency (parse_outputs).

Reads outputs/parsed/main-v1.jsonl + outputs/raw/main-v1.<model>.canon.jsonl,
re-runs parse_canonicalization (with the A5 stage-2 header skip) on each
archived response, and writes outputs/parsed/main-v1r.jsonl. No model is
re-run; extraction fields are byte-identical; the original file is preserved.

Pairing: raw canon records carry meta.item_id/arm + the surface triple, and
were archived in the same order run_matrix appended canonical entries.
Crashed earlier attempts of the same (item, arm) also archived rows before
dying (the record on disk is always the FINAL attempt's), so per key the
TRAILING k archive rows are consumed, where k = the record's canon entries
that received a response (entries without an "error" field). Each pairing is
still guarded by exact surface-triple equality; entries with no matching
archived response (the CANON-FAIL exception path never archived one) are
kept unchanged.
"""

from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path

from llm_backend import response_text
from parse_outputs import parse_canonicalization

OUT = Path(__file__).resolve().parent.parent / "outputs"
MODELS = ("qwen3-8b", "llama31-8b")


def load_archive(model: str):
    q = defaultdict(deque)   # (item_id, arm) -> deque[(surface, text)]
    with open(OUT / "raw" / ("main-v1.%s.canon.jsonl" % model), encoding="utf-8") as f:
        for ln in f:
            rec = json.loads(ln)
            meta = rec.get("meta") or {}
            surface = (meta.get("retrieval") or {}).get("surface")
            key = (meta.get("item_id"), meta.get("arm"))
            q[key].append((surface, response_text(rec.get("response") or {})))
    return q


def main() -> None:
    archives = {m: load_archive(m) for m in MODELS}
    stats = {m: {"entries": 0, "reparsed": 0, "changed": 0, "no_response": 0}
             for m in MODELS}

    src = OUT / "parsed" / "main-v1.jsonl"
    dst = OUT / "parsed" / "main-v1r.jsonl"
    with open(src, encoding="utf-8") as fin, open(dst, "w", encoding="utf-8") as fout:
        for ln in fin:
            r = json.loads(ln)
            m = r["model"]
            queue = archives[m][(r["item_id"], r["arm"])]
            # final attempt = trailing k rows (k = entries that got a response)
            k = sum(1 for e in r["canonical"] if "error" not in e)
            while len(queue) > k:
                queue.popleft()   # discard crashed-earlier-attempt rows
            new_canon = []
            for entry in r["canonical"]:
                stats[m]["entries"] += 1
                if queue and queue[0][0] == entry["surface"]:
                    _, text = queue.popleft()
                    cp = parse_canonicalization(text)
                    new_entry = {"surface": entry["surface"],
                                 "subject_qid": cp.subject,
                                 "property_pid": cp.property,
                                 "object": cp.obj, "parsed": cp.parsed}
                    stats[m]["reparsed"] += 1
                    if (new_entry["subject_qid"], new_entry["property_pid"],
                            new_entry["object"]) != (entry.get("subject_qid"),
                            entry.get("property_pid"), entry.get("object")):
                        stats[m]["changed"] += 1
                    new_canon.append(new_entry)
                else:
                    stats[m]["no_response"] += 1   # CANON-FAIL path: keep as-is
                    new_canon.append(entry)
            r["canonical"] = new_canon
            fout.write(json.dumps(r, ensure_ascii=False) + "\n")

    leftover = {m: sum(len(q) for q in archives[m].values()) for m in MODELS}
    print(json.dumps({"stats": stats, "unconsumed_archive_responses": leftover},
                     indent=2))


if __name__ == "__main__":
    main()
