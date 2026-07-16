"""Pivot-arm MT bridge: main harness (Python 3.14) -> MT venv worker (3.11).

Spawns src/mt_worker.py inside D:\\xlkg-models\\venv-mt (loads IndicTrans2 once,
streams line-JSON over stdio) and caches every translation in
data/mt_cache.sqlite keyed by (model, src_lang, text) — so pivot translations
are computed exactly once and replay byte-identically across runs (same
discipline as the Wikidata cache; the cache ships in the artifact archive).

HF_TOKEN note: the IndicTrans2 repos are gated; the token lives in the USER
environment (set 2026-07-18) and is re-read here because fresh shells/processes
don't always inherit it.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

VENV_PY = Path(r"D:\xlkg-models\venv-mt\Scripts\python.exe")
WORKER = Path(__file__).resolve().parent / "mt_worker.py"
DEFAULT_MODEL = "ai4bharat/indictrans2-indic-en-dist-200M"
CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "mt_cache.sqlite"

# Study codes -> FLORES codes (script tags per admin/mt-backend-verification.md)
FLORES = {
    "hi": "hin_Deva", "bn": "ben_Beng", "te": "tel_Telu", "ta": "tam_Taml",
    "kn": "kan_Knda", "ml": "mal_Mlym", "mr": "mar_Deva", "gu": "guj_Gujr",
    "en": "eng_Latn",
}


class MTBackend:
    """Context manager. translate() checks the cache first; the worker only
    sees cache misses. Worker startup (~model load) happens lazily on the
    first miss, so cache-complete runs never spawn the venv at all."""

    def __init__(self, model: str = DEFAULT_MODEL, cache_path: str | Path = CACHE_PATH):
        self.model = model
        path = Path(cache_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path))
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS mt (model TEXT, src_lang TEXT, text TEXT,"
            " translation TEXT, fetched_at TEXT, PRIMARY KEY (model, src_lang, text))")
        self._db.commit()
        self._proc = None
        self._counter = 0
        self.stats = {"cache_hits": 0, "translated": 0}

    def __enter__(self) -> "MTBackend":
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self) -> None:
        if self._proc is not None:
            self._proc.stdin.close()
            self._proc.wait(timeout=60)
            self._proc = None

    def _ensure_worker(self) -> None:
        if self._proc is not None:
            return
        env = dict(os.environ)
        env.setdefault("HF_HOME", r"D:\xlkg-models\hf")
        env.setdefault("PYTHONIOENCODING", "utf-8")
        if not env.get("HF_TOKEN"):
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                try:
                    env["HF_TOKEN"] = winreg.QueryValueEx(k, "HF_TOKEN")[0]
                except FileNotFoundError:
                    pass
        self._proc = subprocess.Popen(
            [str(VENV_PY), str(WORKER), self.model],
            cwd=str(WORKER.parent), env=env, text=True, encoding="utf-8",
            stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        line = self._proc.stdout.readline().strip()
        while line and line != "READY":  # skip HF migration chatter etc.
            line = self._proc.stdout.readline().strip()
        if line != "READY":
            raise RuntimeError("mt_worker did not become READY")

    def translate(self, text: str, src_lang: str, tgt_lang: str = "en") -> str:
        """src_lang/tgt_lang in study codes (hi, ta, ..., en)."""
        src, tgt = FLORES[src_lang], FLORES[tgt_lang]
        row = self._db.execute(
            "SELECT translation FROM mt WHERE model=? AND src_lang=? AND text=?",
            (self.model, src, text)).fetchone()
        if row is not None:
            self.stats["cache_hits"] += 1
            return row[0]
        self._ensure_worker()
        self._counter += 1
        req = {"id": str(self._counter), "text": text, "src_lang": src, "tgt_lang": tgt}
        self._proc.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
        self._proc.stdin.flush()
        resp = json.loads(self._proc.stdout.readline())
        translation = resp["translation"]
        self._db.execute(
            "INSERT OR REPLACE INTO mt VALUES (?, ?, ?, ?, ?)",
            (self.model, src, text, translation,
             datetime.now(timezone.utc).isoformat(timespec="seconds")))
        self._db.commit()
        self.stats["translated"] += 1
        return translation
