"""Three-way triple classification against Wikidata (PREREGISTRATION.md section 2).

Every predicted triple is classified:
  (i)   IN_GOLD               — matches the gold set (see metrics.py)
  (ii)  TRUE_IN_WIKIDATA      — not in gold, but the (QID, PID, QID/value) statement
                                 exists in Wikidata -> gold-incompleteness signal (C2)
  (iii) CANDIDATE_HALLUCINATION — absent from Wikidata

Also fetches sitelink counts (entity popularity) for the B3 stratification
(pre-registration row 6): bottom-vs-top popularity quartiles.

TODO(day 3-5, after XAlign data lands):
  - batch SPARQL ASK/SELECT queries against https://query.wikidata.org/sparql
    (respect the public endpoint etiquette: batching, User-Agent header, backoff;
    consider a local dump via qwikidata/WDQS mirror if volume demands it)
  - cache all lookups on disk (data/wikidata_cache/) so runs are reproducible
    and the endpoint is hit at most once per statement
  - snapshot date recorded per lookup (Wikidata changes; the paper reports the
    query window)
"""

from __future__ import annotations

from enum import Enum


class TripleClass(Enum):
    IN_GOLD = "in_gold"
    TRUE_IN_WIKIDATA = "true_in_wikidata"
    CANDIDATE_HALLUCINATION = "candidate_hallucination"


def classify_triple(triple, gold_triples, wikidata_client) -> TripleClass:
    raise NotImplementedError("TODO: implement after data lands (see module docstring)")


def sitelink_count(qid: str, wikidata_client) -> int:
    """Entity popularity proxy for the B3 stratification (row 6)."""
    raise NotImplementedError("TODO: SPARQL wikibase:sitelinks lookup, cached")
