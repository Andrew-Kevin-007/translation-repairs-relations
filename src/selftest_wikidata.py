"""Live smoke test for the day-2 Wikidata layer. Run manually: python selftest_wikidata.py

Verifies instrument plumbing against known facts (nothing here scores study data):
  1. wbgetentities fetch + local statement checks (QID object, true vs false)
  2. time-literal matching at mixed precision
  3. sitelink counts (B3)
  4. language-aware candidate search in Tamil and Hindi
  5. three-way classification wiring
  6. cache replay: repeat calls must cost zero network requests
"""

from __future__ import annotations

import sys

from candidates import entity_candidates, format_candidates
from metrics import Triple
from wikidata_check import TripleClass, classify_triple
from wikidata_client import WikidataClient

FAILURES = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, (" — " + detail) if detail else ""))
    if not ok:
        FAILURES.append(name)


def main() -> int:
    c = WikidataClient()

    # 1. statement checks on Douglas Adams (Q42)
    check("Q42 P31 Q5 (human) exists", c.statement_exists("Q42", "P31", "Q5"))
    check("Q42 P31 Q146 (house cat) absent", not c.statement_exists("Q42", "P31", "Q146"))
    check("nonexistent QID is absent", not c.statement_exists("Q999999999999", "P31", "Q5"))

    # 2. time literals (birth date 1952-03-11, day precision)
    check("Q42 P569 1952-03-11 (day)", c.statement_exists("Q42", "P569", "1952-03-11"))
    check("Q42 P569 1952 (year, coarser)", c.statement_exists("Q42", "P569", "1952"))
    check("Q42 P569 1953 rejected", not c.statement_exists("Q42", "P569", "1953"))

    # 3. sitelinks (B3 popularity proxy)
    n = c.sitelink_count("Q42")
    check("Q42 sitelinks > 50", n is not None and n > 50, "got %r" % n)
    check("missing QID -> None", c.sitelink_count("Q999999999999") is None)

    # 4. language-aware search: Chennai in Tamil, Douglas Adams in Hindi
    ta = entity_candidates("சென்னை", "ta", c)
    check("ta search finds Q1352 (Chennai)", any(r["id"] == "Q1352" for r in ta),
          "top ids: %s" % [r["id"] for r in ta[:5]])
    hi = entity_candidates("डगलस एडम्स", "hi", c)
    print("     hi search top ids: %s" % [r["id"] for r in hi[:5]])
    check("candidate formatting non-empty", len(format_candidates(ta).splitlines()) >= 1)

    # 5. classification wiring
    gold = [Triple("Q42", "P800", "Q25169")]
    check("classify: IN_GOLD",
          classify_triple(Triple("Q42", "P800", "Q25169"), gold, c) is TripleClass.IN_GOLD)
    check("classify: TRUE_IN_WIKIDATA",
          classify_triple(Triple("Q42", "P31", "Q5"), gold, c) is TripleClass.TRUE_IN_WIKIDATA)
    check("classify: CANDIDATE_HALLUCINATION",
          classify_triple(Triple("Q42", "P31", "Q146"), gold, c) is TripleClass.CANDIDATE_HALLUCINATION)

    # 6. cache replay: everything above again, zero new network requests
    before = c.stats["network"]
    c.statement_exists("Q42", "P31", "Q5")
    c.sitelink_count("Q42")
    entity_candidates("சென்னை", "ta", c)
    check("cache replay costs zero network", c.stats["network"] == before,
          "network %d -> %d" % (before, c.stats["network"]))

    window = c.cache_date_range()
    print("     stats: %r, query window: %r" % (c.stats, window))
    print("%d checks failed" % len(FAILURES) if FAILURES else "ALL CHECKS PASSED")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
