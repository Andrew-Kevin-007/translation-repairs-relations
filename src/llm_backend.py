"""LLM inference backend: llama.cpp server + raw-generation archive (day 4).

Stack decided in admin/compute-audit.md (llama.cpp GGUF, full GPU offload,
sequential models). Hard pre-registration rule honored here: EVERY raw response
is archived verbatim (RawArchive.append) BEFORE any parsing happens — the B2
"knows-it-but-can't-canonicalize" probe scans these archives, and parse-rule
changes must never require re-running models.

Build gotcha (2026-07-17, llama.cpp b10034): llama-cli auto-enters conversation
mode for chat-template GGUFs; we therefore use llama-server + HTTP, which is
also what the run matrix wants (one resident server per model, many requests).
Qwen3 thinking-mode is disabled via chat_template_kwargs AND stripped by the
parser if it leaks (parse_outputs.strip_think) — raw archive keeps it either way.
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import requests

LLAMA_SERVER = Path(r"D:\xlkg-models\llama.cpp\bin\llama-server.exe")
GGUF_DIR = Path(r"D:\xlkg-models\gguf")
SEED = 20260715


@dataclass(frozen=True)
class ModelSpec:
    name: str                      # short id used in filenames and configs
    gguf: str                      # filename under GGUF_DIR
    template_kwargs: dict = field(default_factory=dict)  # e.g. disable thinking


MODELS = {
    "qwen3-8b": ModelSpec(
        name="qwen3-8b",
        gguf="Qwen3-8B-Q4_K_M.gguf",
        template_kwargs={"enable_thinking": False},
    ),
    "llama31-8b": ModelSpec(
        name="llama31-8b",
        gguf="Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
    ),
}


class LlamaServer:
    """Lifecycle wrapper: spawn llama-server on a model, wait healthy, request,
    terminate. Use as a context manager; models run sequentially (6 GB VRAM)."""

    def __init__(self, spec: ModelSpec, port: int = 8090, ctx: int = 4096,
                 log_dir: str | Path = "../outputs/server-logs"):
        self.spec = spec
        self.port = port
        self.ctx = ctx
        self.log_dir = Path(log_dir)
        self._proc = None
        self._log_handle = None

    def __enter__(self) -> "LlamaServer":
        self.log_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.log_dir / ("%s.%s.log" % (self.spec.name,
                                   datetime.now().strftime("%Y%m%d-%H%M%S")))
        self._log_handle = open(log_path, "w", encoding="utf-8")
        self._proc = subprocess.Popen(
            [str(LLAMA_SERVER), "-m", str(GGUF_DIR / self.spec.gguf),
             "--port", str(self.port), "-ngl", "99", "-c", str(self.ctx),
             "--seed", str(SEED), "-np", "1"],
            stdout=self._log_handle, stderr=subprocess.STDOUT)
        deadline = time.time() + 300  # first load streams ~5 GB from disk
        while time.time() < deadline:
            if self._proc.poll() is not None:
                raise RuntimeError("llama-server died on startup; see %s" % log_path)
            try:
                if requests.get(self._url("/health"), timeout=3).status_code == 200:
                    return self
            except requests.RequestException:
                pass
            time.sleep(2)
        raise RuntimeError("llama-server not healthy after 300s; see %s" % log_path)

    def __exit__(self, *exc):
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        if self._log_handle is not None:
            self._log_handle.close()

    def _url(self, path: str) -> str:
        return "http://127.0.0.1:%d%s" % (self.port, path)

    def chat(self, messages: list[dict], max_tokens: int = 256) -> dict:
        """Deterministic chat completion. Returns the server's raw response
        JSON — archive it verbatim before touching the content."""
        payload = {
            "messages": messages,
            "temperature": 0,
            "seed": SEED,
            "max_tokens": max_tokens,
        }
        if self.spec.template_kwargs:
            payload["chat_template_kwargs"] = self.spec.template_kwargs
        resp = requests.post(self._url("/v1/chat/completions"), json=payload,
                             timeout=600)
        if resp.status_code >= 400:
            # surface the server's own error body — a bare status code cost us
            # a run-halting mystery on 2026-07-17
            raise RuntimeError("llama-server HTTP %d: %s"
                               % (resp.status_code, resp.text[:500]))
        return resp.json()


def response_text(response: dict) -> str:
    """Content of a /v1/chat/completions response."""
    return response["choices"][0]["message"]["content"]


class RawArchive:
    """Append-only JSONL of verbatim generations. One file per
    (model, lang, arm) in the run matrix; selftests use their own prefix."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, spec: ModelSpec, request_messages: list[dict],
               response: dict, meta: dict | None = None) -> None:
        record = {
            "ts_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "model": spec.name,
            "gguf": spec.gguf,
            "seed": SEED,
            "request_messages": request_messages,
            "response": response,      # verbatim server JSON
            "meta": meta or {},
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
