"""Three-way triple classification against Wikidata (PREREGISTRATION.md section 2).

Every predicted triple is classified:
  (i)   IN_GOLD               — matches the gold set (see metrics.py)
  (ii)  TRUE_IN_WIKIDATA      — not in gold, but the (QID, PID, QID/value) statement
                                 exists in Wikidata -> gold-incompleteness signal (C2)
  (iii) CANDIDATE_HALLUCINATION — absent from Wikidata

Also fetches sitelink counts (entity popularity) for the B3 stratification
(pre-registration row 6): bottom-vs-top popularity quartiles.

Implemented day 2 on top of the cached client (src/wikidata_client.py; decision
record admin/entity-retrieval-design.md). Reproducibility: all lookups replay
from data/wikidata_cache/, and client.cache_date_range() supplies the query
window the paper reports. These classifications feed only the SECONDARY C2/
hallucination analyses — primary GRR metrics never touch the live Wikidata.
"""

from __future__ import annotations

from enum import Enum

from metrics import Triple
from wikidata_client import WikidataClient


class TripleClass(Enum):
    IN_GOLD = "in_gold"
    TRUE_IN_WIKIDATA = "true_in_wikidata"
    CANDIDATE_HALLUCINATION = "candidate_hallucination"


def classify_triple(triple: Triple, gold_triples: list[Triple],
                    wikidata_client: WikidataClient) -> TripleClass:
    """`triple` is a strict-form Triple (QIDs/PIDs). Gold membership uses the
    same exact-tuple view as metrics.py's strict triple metric."""
    key = (triple.subject, triple.property, triple.obj)
    if any((g.subject, g.property, g.obj) == key for g in gold_triples):
        return TripleClass.IN_GOLD
    if wikidata_client.statement_exists(triple.subject, triple.property, triple.obj):
        return TripleClass.TRUE_IN_WIKIDATA
    return TripleClass.CANDIDATE_HALLUCINATION


def sitelink_count(qid: str, wikidata_client: WikidataClient) -> int | None:
    """Entity popularity proxy for the B3 stratification (row 6).
    None = QID does not exist."""
    return wikidata_client.sitelink_count(qid)
