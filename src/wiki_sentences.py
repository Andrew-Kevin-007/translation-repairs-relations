"""Wikipedia sentence sourcing for the SPARQL gold-rebuild fallback (Gate 1).

Only used if XAlign access does not materialize (admin/xalign-fallback-pack.md,
step 3): fetch the lead section of a target-language Wikipedia article to mine
candidate sentences for distant fact alignment. Same reproducibility discipline
as the Wikidata layer: every response cached with a UTC timestamp in the same
sqlite store (namespace 'wiki'), query window reportable.

Endpoint: the Wikimedia REST summary API (per-language hosts), e.g.
https://ta.wikipedia.org/api/rest_v1/page/summary/<title>  -> lead extract.
Titles come from the Wikidata sitelinks of sampled entities (wikidata_client).
"""

from __future__ import annotations

import urllib.parse

from wikidata_client import WikidataClient


def lead_extract(client: WikidataClient, lang: str, title: str) -> str | None:
    """Plain-text lead extract of an article, cached. None if missing."""
    key = "%s:%s" % (lang, title)
    cached = client._cache_get("wiki", key)
    if cached is not None:
        return cached.get("extract")
    url = "https://%s.wikipedia.org/api/rest_v1/page/summary/%s" % (
        lang, urllib.parse.quote(title.replace(" ", "_"), safe=""))
    try:
        data = client._request_json(url, {})
    except RuntimeError:
        data = {}
    record = {"extract": data.get("extract") or None,
              "description": data.get("description"),
              "pageid": data.get("pageid")}
    client._cache_put("wiki", key, record)
    return record["extract"]


def sentences_from_extract(extract: str) -> list[str]:
    """Conservative sentence split for the fallback pipeline. Indic scripts use
    the danda (U+0964) and '.'; we split on both plus '?' '!'. Deliberately
    simple and deterministic — alignment quality is audited downstream
    (Tamil-first, per the fallback pack), not assumed here."""
    out = []
    buf = []
    for ch in extract:
        buf.append(ch)
        if ch in ".!?।":
            s = "".join(buf).strip()
            if len(s) >= 20:
                out.append(s)
            buf = []
    tail = "".join(buf).strip()
    if len(tail) >= 20:
        out.append(tail)
    return out
