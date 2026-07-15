"""Candidate retrieval for stage-2 canonicalization (day 2).

The LLM never generates QIDs freely — it disambiguates among candidates
retrieved here (src/prompts/canonicalize.txt). Retrieval is identical across
arms D/P/E by construction; only the query surface differs. Decision record:
admin/entity-retrieval-design.md.
"""

from __future__ import annotations

from wikidata_client import WikidataClient


def entity_candidates(surface: str, lang: str, client: WikidataClient,
                      limit: int = 8) -> list[dict]:
    """Search in the source language first; top up from English if short
    (extraction output may surface an English form even in arm D). Deduped
    by QID, source-language hits first."""
    results = list(client.search_entities(surface, lang, limit=limit))
    if len(results) < limit and lang != "en":
        seen = {r["id"] for r in results}
        for r in client.search_entities(surface, "en", limit=limit):
            if r["id"] not in seen:
                results.append(r)
                seen.add(r["id"])
            if len(results) >= limit:
                break
    return results[:limit]


def property_candidates(surface: str, client: WikidataClient,
                        limit: int = 8) -> list[dict]:
    """EXPLORATION ONLY. At scoring time the property candidate list is the
    gold dataset's closed relation inventory (enumerated when data lands,
    day 3+) — free property search never feeds a scored run (design record,
    section 5)."""
    return client.search_entities(surface, "en", limit=limit, entity_type="property")


def format_candidates(cands: list[dict]) -> str:
    """Render candidates for the canonicalize.txt placeholders, one per line:
    'Q1352: Chennai — capital of Tamil Nadu, India'."""
    if not cands:
        return "(none found)"
    lines = []
    for c in cands:
        desc = c.get("description") or "no description"
        lines.append("%s: %s — %s" % (c["id"], c.get("label") or "?", desc))
    return "\n".join(lines)
