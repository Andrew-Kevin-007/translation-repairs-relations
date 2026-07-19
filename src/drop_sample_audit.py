"""Finding 9 (Zeus pre-review): classify a 50-item drop sample into
drift vs procedural, to test whether the 'drift-dominated' claim in main.tex
§3.1 holds. OFFLINE + deterministic: uses only the frozen XAlign source and
the gold's kept-ID gaps to recover the exact dropped items (no gold rebuild,
no Wikidata re-query). Reproduces the drop set exactly (verified against the
per-language drop counts).

Discriminator for finding 9's specific concern (normalize_literal misses unit
quantities): an object string that CONTAINS A DIGIT but normalize_literal()
returns None is a numeric/quantity literal the tool could not parse -> it gets
mis-routed to entity resolution and fails as 'object-unresolved' -> that is a
PROCEDURAL drop, not KB drift. Clean literals (date/number/year that
normalize_literal handles) and pure entity names (no digits) that drop reflect
genuine KB drift (statement/entity changed in live Wikidata).
"""
import sys, json, re, random
from pathlib import Path

sys.path.insert(0, r"D:\Research\xlkg\src")
from gold_canonicalize import normalize_literal   # faithful to the build

XALIGN = Path(r"D:\xlkg-data\xalign\v2.0")
GOLD = Path(r"D:\xlkg-data\gold")
LANGS = ["hi", "bn", "te", "ta", "kn", "ml", "mr", "gu", "en"]

def kept_line_numbers(lang):
    nums = set()
    for ln in (GOLD / f"{lang}_test.jsonl").read_text(encoding="utf-8").splitlines():
        if ln.strip():
            m = re.search(r"-test-(\d+)$", json.loads(ln)["id"])
            nums.add(int(m.group(1)))
    return nums

# ---- recover the exact dropped items via kept-ID gaps ----
dropped = []
for lang in LANGS:
    src = [ln for ln in (XALIGN / lang / "test.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    kept = kept_line_numbers(lang)
    for i, ln in enumerate(src, 1):          # i == source line number == kept id suffix
        if i in kept:
            continue
        it = json.loads(ln)
        dropped.append({"lang": lang, "line": i, "sentence": it.get("sentence", ""),
                        "facts": it.get("facts", [])})
    assert len(kept) == sum(1 for _ in (GOLD/f"{lang}_test.jsonl").read_text(encoding='utf-8').splitlines() if _.strip())

print(f"total dropped recovered: {len(dropped)} (expected 660)")
from collections import Counter
print("by lang:", dict(Counter(d["lang"] for d in dropped)))

# ---- procedural-signature detector (finding 9's normalize_literal concern) ----
# a genuine QUANTITY literal = a number followed by a unit (what Wikidata stores
# as a quantity value and what normalize_literal cannot parse -> finding 9's
# named procedural failure). Proper names that merely CONTAIN a digit
# ("1996 Summer Olympics", "FC Schalke 04", "Apollo 11") are entities, not this.
QTY_UNIT = re.compile(
    r"^[+-]?\d+([.,]\d+)?\s*"
    r"(%|°|years?|yrs?|months?|weeks?|days?|hours?|minutes?|seconds?|"
    r"km|kmh|kph|mph|cm|mm|nm|kg|g|mg|lbs?|tonnes?|tons?|"
    r"m|metres?|meters?|ft|feet|foot|in|inch(?:es)?|miles?|"
    r"goals?|points?|pts?|matches|caps|wickets|runs|medals?|"
    r"seats?|votes?|episodes?|albums?)\b", re.I)

def obj_kind(obj):
    s = (obj or "").strip()
    if normalize_literal(s) is not None:
        return "clean-literal"          # date/number/year the tool parses (drift if dropped)
    if QTY_UNIT.match(s):
        return "numeric-quantity"       # true normalize_literal miss => PROCEDURAL
    return "entity"                     # name (incl. names with embedded digits) => drift if dropped

def classify(item):
    kinds = [obj_kind(f.get("object", "")) for f in item["facts"]]
    proc = [f["object"] for f, k in zip(item["facts"], kinds) if k == "numeric-quantity"]
    if proc:
        return "PROCEDURAL", "unit-quantity literal normalize_literal can't parse: " + "; ".join(proc[:3])
    return "DRIFT", "objects are entities / clean literals -> drop reflects KB change"

# ---- deterministic 50-item sample from the full pool ----
random.seed(20260719)
sample = random.sample(dropped, 50)
sample.sort(key=lambda d: (d["lang"], d["line"]))

rows = []
for d in sample:
    label, why = classify(d)
    facts_str = " | ".join(f"{f.get('subject','')} —[{f.get('predicate','')}]→ {f.get('object','')}" for f in d["facts"])
    rows.append((d["lang"], d["line"], label, why, facts_str))

n_proc = sum(1 for r in rows if r[2] == "PROCEDURAL")
n_drift = 50 - n_proc
print(f"\n=== 50-ITEM SAMPLE CLASSIFICATION (seed 20260719) ===")
print(f"DRIFT: {n_drift}/50   PROCEDURAL: {n_proc}/50\n")
for lang, line, label, why, facts in rows:
    tag = "PROC" if label == "PROCEDURAL" else "drift"
    print(f"[{tag}] {lang}-{line:04d}: {facts}")
    if label == "PROCEDURAL":
        print(f"         -> {why}")

# also: full-pool procedural rate (all 660), for the paper's quantitative claim
pool_proc = sum(1 for d in dropped if classify(d)[0] == "PROCEDURAL")
print(f"\n=== FULL POOL (660 drops) ===")
print(f"procedural-signature items: {pool_proc}/{len(dropped)} = {100*pool_proc/len(dropped):.1f}%")
print(f"drift-signature items:      {len(dropped)-pool_proc}/{len(dropped)} = {100*(len(dropped)-pool_proc)/len(dropped):.1f}%")
