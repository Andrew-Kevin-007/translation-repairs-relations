"""Stage 2: canonicalize extracted surface triples to Wikidata IDs.

The LLM only disambiguates among candidates retrieved OUTSIDE the model
(candidates.py; design record admin/entity-retrieval-design.md) — it never
free-generates QIDs. Same stage for every arm; only the surface language of
the query differs (arm D: source language; arms P/E: English).

Property candidates: the closed relation inventory of the gold dataset once it
lands (design record §5). Until then `property_candidates` free search is used
by selftests only, clearly flagged.
"""

from __future__ import annotations

from candidates import entity_candidates, format_candidates, property_candidates
from parse_outputs import CanonParse, parse_canonicalization
from pathlib import Path

_TEMPLATE_CACHE: dict[str, str] = {}


def load_template() -> str:
    if "canon" not in _TEMPLATE_CACHE:
        lines = (Path(__file__).resolve().parent / "prompts" / "canonicalize.txt")\
            .read_text(encoding="utf-8").splitlines()
        _TEMPLATE_CACHE["canon"] = "\n".join(
            l for l in lines if not l.startswith("#")).strip()
    return _TEMPLATE_CACHE["canon"]


def build_canon_messages(surface_triple: tuple[str, str, str], lang: str,
                         wd_client, property_inventory: list[dict] | None = None,
                         limit: int = 8) -> tuple[list[dict], dict]:
    """Retrieve candidates and render the stage-2 prompt.
    Returns (chat messages, retrieval_meta for the raw archive)."""
    s, r, o = surface_triple
    s_cands = entity_candidates(s, lang, wd_client, limit=limit)
    o_cands = entity_candidates(o, lang, wd_client, limit=limit)
    if property_inventory is not None:
        p_cands = property_inventory  # closed set, already [{id,label,description}]
    else:
        # selftest/exploration path only (no dataset inventory yet)
        p_cands = property_candidates(r, wd_client, limit=limit)
    prompt = load_template().format(
        subject=s, relation=r, obj=o, object=o,
        subject_candidates=format_candidates(s_cands),
        object_candidates=format_candidates(o_cands),
        property_candidates=format_candidates(p_cands))
    meta = {"surface": [s, r, o], "lang": lang,
            "subject_candidates": [c["id"] for c in s_cands],
            "object_candidates": [c["id"] for c in o_cands],
            "property_candidates": [c["id"] for c in p_cands],
            "closed_inventory": property_inventory is not None}
    return [{"role": "user", "content": prompt}], meta


def canonicalize_triple(server, archive, surface_triple, lang, wd_client,
                        property_inventory=None, meta=None) -> CanonParse:
    """Full stage-2 for one triple: retrieve -> prompt -> archive -> parse."""
    messages, retrieval_meta = build_canon_messages(
        surface_triple, lang, wd_client, property_inventory)
    resp = server.chat(messages, max_tokens=128)
    record_meta = dict(meta or {})
    record_meta["retrieval"] = retrieval_meta
    archive.append(server.spec, messages, resp, meta=record_meta)
    from llm_backend import response_text
    return parse_canonicalization(response_text(resp))
