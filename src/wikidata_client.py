"""Cached Wikidata access layer (day 2).

Design record: admin/entity-retrieval-design.md. Summary of the decisions:
  - candidate retrieval via wbsearchentities (language-aware, all of Wikidata);
  - statement verification via wbgetentities (one cached fetch per subject QID,
    claims checked locally; sitelink counts for B3 come from the same fetch);
  - every response disk-cached in data/wikidata_cache/ with a UTC fetch
    timestamp; the cache is archived at submission and cache_date_range()
    supplies the query window the paper reports.

Nothing here scores anything: this is instrument plumbing. Literal-matching
rules freeze on day 8 with the prompts (see design record, section 3).
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import requests

API_URL = "https://www.wikidata.org/w/api.php"
SPARQL_URL = "https://query.wikidata.org/sparql"

_DEFAULT_CACHE = Path(__file__).resolve().parent.parent / "data" / "wikidata_cache" / "wikidata_cache.sqlite"

_QID_RE = re.compile(r"^Q[1-9][0-9]*$")
_DATE_RE = re.compile(r"^([+-]?\d{1,4})(?:-(\d{2}))?(?:-(\d{2}))?$")


def _user_agent() -> str:
    # Contact injected from the environment, never stored in the repo (double-blind).
    contact = os.environ.get("XLKG_CONTACT", "contact: see repository")
    return "xlkg-harness/0.1 (%s) python-requests/%s" % (contact, requests.__version__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize_str(s: str) -> str:
    return unicodedata.normalize("NFKC", s).casefold().strip()


class WikidataClient:
    """Serial, polite, aggressively cached. One instance per run."""

    def __init__(self, cache_path: str | Path | None = None,
                 politeness_delay: float = 0.1, timeout: float = 30.0):
        path = Path(cache_path) if cache_path else _DEFAULT_CACHE
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path))
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS kv ("
            " ns TEXT NOT NULL, key TEXT NOT NULL, val TEXT NOT NULL,"
            " fetched_at TEXT NOT NULL, PRIMARY KEY (ns, key))")
        self._db.commit()
        self._delay = politeness_delay
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers["User-Agent"] = _user_agent()
        self.stats = {"network": 0, "cache_hits": 0}

    # ---------- cache ----------

    def _cache_get(self, ns: str, key: str):
        row = self._db.execute(
            "SELECT val FROM kv WHERE ns = ? AND key = ?", (ns, key)).fetchone()
        if row is None:
            return None
        self.stats["cache_hits"] += 1
        return json.loads(row[0])

    def _cache_put(self, ns: str, key: str, val) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO kv (ns, key, val, fetched_at) VALUES (?, ?, ?, ?)",
            (ns, key, json.dumps(val, ensure_ascii=False, sort_keys=True), _utc_now()))
        self._db.commit()

    def cache_date_range(self) -> tuple[str, str] | None:
        """(first, last) UTC fetch timestamps — the query window the paper reports."""
        lo, hi = self._db.execute("SELECT MIN(fetched_at), MAX(fetched_at) FROM kv").fetchone()
        return (lo, hi) if lo else None

    # ---------- HTTP with backoff ----------

    def _request_json(self, url: str, params: dict, method: str = "GET") -> dict:
        last_err = None
        for attempt in range(6):
            try:
                if method == "POST":
                    resp = self._session.post(url, data=params, timeout=self._timeout)
                else:
                    resp = self._session.get(url, params=params, timeout=self._timeout)
                self.stats["network"] += 1
            except requests.RequestException as e:
                last_err = e
                time.sleep(2 ** attempt)
                continue
            if resp.status_code in (429, 500, 502, 503, 504):
                retry_after = resp.headers.get("Retry-After")
                time.sleep(float(retry_after) if retry_after else 2 ** attempt)
                continue
            resp.raise_for_status()
            data = resp.json()
            # MediaWiki reports maxlag as an error body on HTTP 200
            if isinstance(data, dict) and data.get("error", {}).get("code") == "maxlag":
                retry_after = resp.headers.get("Retry-After")
                time.sleep(float(retry_after) if retry_after else 2 ** attempt)
                continue
            time.sleep(self._delay)  # politeness: only on real network hits
            return data
        raise RuntimeError("Wikidata request kept failing after retries: %r (%s)" % (params, last_err))

    # ---------- entities (wbgetentities, simplified + cached per QID) ----------

    @staticmethod
    def _simplify_entity(ent: dict) -> dict:
        """Compact form stored in the cache: mainsnak values per property,
        sitelink count, labels. Enough for statement checks, C2, and B3."""
        claims = {}
        for pid, statements in ent.get("claims", {}).items():
            vals = []
            for st in statements:
                snak = st.get("mainsnak", {})
                if snak.get("snaktype") != "value":
                    continue
                dv = snak.get("datavalue", {})
                t, v = dv.get("type"), dv.get("value")
                if t == "wikibase-entityid":
                    vals.append({"t": "q", "v": v.get("id")})
                elif t == "time":
                    vals.append({"t": "time", "v": v.get("time"), "p": v.get("precision")})
                elif t == "quantity":
                    vals.append({"t": "qty", "v": v.get("amount")})
                elif t == "monolingualtext":
                    vals.append({"t": "str", "v": v.get("text")})
                elif t == "string":
                    vals.append({"t": "str", "v": v})
                else:
                    vals.append({"t": "other", "v": json.dumps(v, sort_keys=True)})
            claims[pid] = vals
        labels = {lang: d.get("value", "") for lang, d in ent.get("labels", {}).items()}
        return {"claims": claims, "sitelinks": len(ent.get("sitelinks", {})), "labels": labels}

    def get_entities(self, qids: list[str]) -> dict[str, dict | None]:
        """Fetch (or replay from cache) simplified entities. None = no such QID."""
        out: dict[str, dict | None] = {}
        missing: list[str] = []
        for qid in dict.fromkeys(qids):  # dedupe, keep order
            cached = self._cache_get("entity", qid)
            if cached is not None:
                out[qid] = None if cached.get("missing") else cached
            else:
                missing.append(qid)
        for i in range(0, len(missing), 50):
            chunk = missing[i:i + 50]
            data = self._request_json(API_URL, {
                "action": "wbgetentities", "ids": "|".join(chunk),
                "props": "claims|sitelinks|labels", "format": "json", "maxlag": 5,
            })
            entities = data.get("entities", {})
            for qid in chunk:
                ent = entities.get(qid)
                if ent is None or "missing" in ent:
                    self._cache_put("entity", qid, {"missing": True})
                    out[qid] = None
                else:
                    simple = self._simplify_entity(ent)
                    self._cache_put("entity", qid, simple)
                    out[qid] = simple
        return out

    def sitelink_count(self, qid: str) -> int | None:
        """Entity popularity proxy for the B3 quartiles (pre-reg row 6)."""
        ent = self.get_entities([qid]).get(qid)
        return None if ent is None else ent["sitelinks"]

    def statement_exists(self, subject_qid: str, pid: str, obj: str) -> bool:
        """Does (subject, property, object) exist as a Wikidata mainsnak?
        Literal-matching rules per the design record, section 3."""
        if not _QID_RE.match(subject_qid or ""):
            return False
        ent = self.get_entities([subject_qid]).get(subject_qid)
        if ent is None:
            return False
        return any(_value_matches(v, obj) for v in ent["claims"].get(pid, []))

    # ---------- search (wbsearchentities, cached per query) ----------

    def search_entities(self, text: str, lang: str, limit: int = 8,
                        entity_type: str = "item") -> list[dict]:
        """Language-aware candidate search. Returns [{id, label, description}]."""
        key = json.dumps([text, lang, limit, entity_type], ensure_ascii=False)
        cached = self._cache_get("search", key)
        if cached is not None:
            return cached
        data = self._request_json(API_URL, {
            "action": "wbsearchentities", "search": text, "language": lang,
            "uselang": lang, "type": entity_type, "limit": limit,
            "format": "json", "maxlag": 5,
        })
        results = [{"id": r.get("id"),
                    "label": r.get("label", ""),
                    "description": r.get("description", "")}
                   for r in data.get("search", [])]
        self._cache_put("search", key, results)
        return results

    # ---------- SPARQL (thin helper; nothing primary depends on it) ----------

    def sparql(self, query: str) -> dict:
        cached = self._cache_get("sparql", query)
        if cached is not None:
            return cached
        data = self._request_json(SPARQL_URL, {"query": query, "format": "json"}, method="POST")
        self._cache_put("sparql", query, data)
        return data


def _value_matches(val: dict, obj: str) -> bool:
    obj = (obj or "").strip()
    t = val.get("t")
    if t == "q":
        return val.get("v") == obj
    if t == "time":
        return _time_matches(val.get("v") or "", int(val.get("p") or 11), obj)
    if t == "qty":
        try:
            a, b = float(val.get("v")), float(obj)
        except (TypeError, ValueError):
            return False
        return abs(a - b) <= 1e-6 * max(1.0, abs(a), abs(b))
    if t == "str":
        return _normalize_str(val.get("v") or "") == _normalize_str(obj)
    return False


def _time_matches(wd_time: str, wd_precision: int, obj: str) -> bool:
    """Compare at the coarser of (claim precision, prediction granularity).
    Wikidata times look like '+1952-03-11T00:00:00Z'; precision 9=year,
    10=month, 11=day."""
    m = _DATE_RE.match(obj)
    if not m:
        return False
    year, month, day = m.group(1), m.group(2), m.group(3)
    wm = re.match(r"^([+-]?\d+)-(\d{2})-(\d{2})T", wd_time)
    if not wm:
        return False
    wd_y, wd_m, wd_d = wm.group(1), wm.group(2), wm.group(3)
    obj_precision = 11 if day else (10 if month else 9)
    precision = min(wd_precision, obj_precision)
    if int(year) != int(wd_y):
        return False
    if precision >= 10 and int(month or 0) != int(wd_m):
        return False
    if precision >= 11 and int(day or 0) != int(wd_d):
        return False
    return True
