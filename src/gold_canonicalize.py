"""Gold canonicalization: XAlign v2.0 test splits -> dataset.py contract.

XAlign gold facts are English label strings (subject / predicate / object);
the pipeline contract (dataset.py) wants Wikidata IDs:
    {"id", "lang", "sentence", "gold": [{"subject_qid", "property_pid", "object"}]}

Deterministic procedure (no LLM anywhere near the instrument):
  1. predicate label -> PID via wbsearchentities(type=property); accepted only
     on exact (casefolded) label match, else flagged for manual review.
  2. subject label -> QID via wbsearchentities(type=item); each candidate is
     scored by how many of the item's own gold facts it can corroborate from
     its Wikidata claims (labels for entity objects, frozen literal rules for
     dates/quantities). Highest score wins; score 0 = unresolved.
  3. object -> QID recovered from the chosen subject's claims for that PID
     (label match), never by free search: XAlign facts were built FROM
     Wikidata, so the true value sits in the subject's claims unless the
     statement changed since the 2020/2021 dumps. Literals are normalized
     ("20 October 1981" -> "1981-10-20") and kept as strings.

Strict mode (default): an item is kept only if ALL its facts resolve, so the
gold never carries silently-missing facts into recall denominators. Every
drop is counted and reported per language in <out>/<lang>_stats.json.

Usage (from src/):
  python gold_canonicalize.py --xalign D:/xlkg-data/xalign/v2.0 \
      --out D:/xlkg-data/gold --langs ta,hi --limit 15
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

from wikidata_client import WikidataClient, _value_matches

MONTHS = {m.lower(): i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"])}

_NUM_RE = re.compile(r"^[+-]?\d+(\.\d+)?$")
_QID_RE = re.compile(r"^Q[1-9][0-9]*$")

# Wikidata renamed these properties after XAlign's 2020/2021 snapshot, so
# exact-label search misses them. Every override was verified 2026-07-17
# against the live property registry (admin/gold-adaptation-log.md):
#   P527  "has part(s)"               aliases include "has part"            (verbatim)
#   P140  "religion or worldview"     aliases include "religion"            (verbatim)
#   P607  "participated in conflict"  aliases include "conflict"            (verbatim)
#   P1029 "crew members"              = "crew member(s)" with (s) resolved  (near-verbatim)
#   P118  "league or competition"     no verbatim alias; sole property for
#         sports-league membership — semantic acceptance, audit-flagged
# Deliberately NOT mapped: "astronaut mission" (P450 deleted from Wikidata),
# "victory" (no property carries that label or alias today).
VERIFIED_LABEL_DRIFT = {"has part": "P527", "religion": "P140",
                        "conflict": "P607", "crew member(s)": "P1029",
                        "league": "P118"}


def norm(s: str) -> str:
    return unicodedata.normalize("NFKC", s or "").casefold().strip()


def normalize_literal(obj: str) -> str | None:
    """Date/number labels -> the literal format metrics.py compares against.
    Returns None when the string is not a literal (i.e., an entity label)."""
    s = (obj or "").strip()
    if _NUM_RE.match(s):
        return s
    # "20 October 1981" / "October 1981" / "1981"
    m = re.match(r"^(?:(\d{1,2})\s+)?([A-Za-z]+)\s+(\d{1,4})$", s)
    if m and m.group(2).lower() in MONTHS:
        day, mon, year = m.group(1), MONTHS[m.group(2).lower()], int(m.group(3))
        if day:
            return "%04d-%02d-%02d" % (year, mon, int(day))
        return "%04d-%02d" % (year, mon)
    if re.match(r"^\d{3,4}$", s):
        return s
    return None


class GoldCanonicalizer:
    def __init__(self, client: WikidataClient):
        self.wd = client
        self.pred: dict[str, dict] = {}       # label -> {pid, match, wd_label}

    # ---------- predicates ----------

    def predicate_pid(self, label: str) -> str | None:
        rec = self.pred.get(label)
        if rec is None:
            rec = self._resolve_predicate(label)
            self.pred[label] = rec
        return rec["pid"]

    def _resolve_predicate(self, label: str) -> dict:
        if label in VERIFIED_LABEL_DRIFT:
            return {"pid": VERIFIED_LABEL_DRIFT[label], "match": "drift-override",
                    "wd_label": label}
        hits = self.wd.search_entities(label, lang="en", limit=5,
                                       entity_type="property")
        for h in hits:
            if norm(h.get("label")) == norm(label):
                return {"pid": h["id"], "match": "exact", "wd_label": h["label"]}
        # alias hits come back with the canonical label; accept a lone hit,
        # flagged, so the review table shows exactly what needs human eyes
        if len(hits) == 1:
            return {"pid": hits[0]["id"], "match": "alias-or-fuzzy",
                    "wd_label": hits[0]["label"]}
        return {"pid": None, "match": "none",
                "wd_label": hits[0]["label"] if hits else ""}

    # ---------- entity-object matching against a subject's claims ----------

    def _claim_object_qid(self, ent: dict, pid: str, obj_label: str) -> str | None:
        vals = [v.get("v") for v in ent["claims"].get(pid, []) if v.get("t") == "q"]
        vals = [v for v in vals if v and _QID_RE.match(v)]
        if not vals:
            return None
        labels = self.wd.get_entities(vals)
        for qid in vals:
            lab = labels.get(qid)
            if lab and norm(lab["labels"].get("en", "")) == norm(obj_label):
                return qid
        return None

    def _fact_supported(self, ent: dict, pid: str, obj: str) -> bool:
        lit = normalize_literal(obj)
        if lit is not None:
            return any(_value_matches(v, lit) for v in ent["claims"].get(pid, []))
        return self._claim_object_qid(ent, pid, obj) is not None

    # ---------- subjects ----------

    def resolve_subject(self, label: str, facts: list[dict]) -> tuple[str | None, int]:
        """Pick the search candidate corroborated by the most gold facts.
        Returns (qid | None, corroborated_count)."""
        hits = self.wd.search_entities(label, lang="en", limit=8)
        qids = [h["id"] for h in hits if h.get("id") and _QID_RE.match(h["id"])]
        ents = self.wd.get_entities(qids)          # one batched fetch, not eight
        best_qid, best_score = None, 0
        for qid in qids:
            ent = ents.get(qid)
            if ent is None:
                continue
            score = 0
            for f in facts:
                pid = self.predicate_pid(f["predicate"])
                if pid and self._fact_supported(ent, pid, f["object"]):
                    score += 1
            if score > best_score:                 # ties keep search order
                best_qid, best_score = qid, score
        return best_qid, best_score

    # ---------- items ----------

    def convert_item(self, item: dict) -> tuple[list[dict] | None, str]:
        """-> (gold list, "ok") or (None, drop_reason)."""
        facts = item.get("facts") or []
        if not facts:
            return None, "no-facts"
        subjects = {f["subject"] for f in facts}
        gold: list[dict] = []
        for subj in subjects:
            sub_facts = [f for f in facts if f["subject"] == subj]
            qid, score = self.resolve_subject(subj, sub_facts)
            if qid is None or score == 0:
                return None, "subject-unresolved"
            ent = self.wd.get_entities([qid]).get(qid)
            for f in sub_facts:
                pid = self.predicate_pid(f["predicate"])
                if pid is None:
                    return None, "predicate-unresolved"
                lit = normalize_literal(f["object"])
                if lit is not None:
                    if not any(_value_matches(v, lit) for v in ent["claims"].get(pid, [])):
                        return None, "literal-not-in-claims"
                    gold.append({"subject_qid": qid, "property_pid": pid, "object": lit})
                else:
                    obj_qid = self._claim_object_qid(ent, pid, f["object"])
                    if obj_qid is None:
                        return None, "object-unresolved"
                    gold.append({"subject_qid": qid, "property_pid": pid, "object": obj_qid})
        return gold, "ok"


def run_language(canon: GoldCanonicalizer, xalign_dir: Path, out_dir: Path,
                 lang: str, limit: int | None) -> dict:
    src = xalign_dir / lang / "test.jsonl"
    lines = [ln for ln in src.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if limit:
        lines = lines[:limit]
    kept, drops = [], {}
    for i, ln in enumerate(lines, 1):
        item = json.loads(ln)
        gold, reason = canon.convert_item(item)
        if gold is None:
            drops[reason] = drops.get(reason, 0) + 1
            continue
        kept.append({"id": "%s-test-%04d" % (lang, i), "lang": lang,
                     "sentence": item["sentence"], "gold": gold})
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / ("%s_test.jsonl" % lang)
    out.write_text("".join(json.dumps(k, ensure_ascii=False) + "\n" for k in kept),
                   encoding="utf-8")
    stats = {"lang": lang, "source_items": len(lines), "kept": len(kept),
             "kept_pct": round(100.0 * len(kept) / max(1, len(lines)), 1),
             "drops": drops}
    (out_dir / ("%s_stats.json" % lang)).write_text(
        json.dumps(stats, indent=2), encoding="utf-8")
    return stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xalign", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--langs", required=True, help="comma list, e.g. ta,hi,bn")
    ap.add_argument("--limit", type=int, default=None,
                    help="first N items only (smoke test)")
    args = ap.parse_args()

    canon = GoldCanonicalizer(WikidataClient())
    langs = [l.strip() for l in args.langs.split(",") if l.strip()]
    for lang in langs:
        stats = run_language(canon, Path(args.xalign), Path(args.out), lang, args.limit)
        print(json.dumps(stats, ensure_ascii=False))
    pred_table = {lbl: rec for lbl, rec in sorted(canon.pred.items())}
    # per-invocation filename so parallel per-language workers never clobber
    # each other; fragments are merged when the inventory is built
    Path(args.out, "predicate_map.%s.json" % "-".join(langs)).write_text(
        json.dumps(pred_table, indent=2, ensure_ascii=False), encoding="utf-8")
    flagged = {l: r for l, r in pred_table.items() if r["match"] != "exact"}
    print("predicates: %d total, %d flagged for review"
          % (len(pred_table), len(flagged)))
    for l, r in flagged.items():
        print("  REVIEW: %r -> %s (%s, wd_label=%r)"
              % (l, r["pid"], r["match"], r["wd_label"]))


if __name__ == "__main__":
    main()
