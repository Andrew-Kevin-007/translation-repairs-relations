"""End-to-end LLM instrument dry run (day 4). Run: python selftest_llm.py

Exercises the full chain on SYNTHETIC English sentences (no study data, which
hasn't landed; prompts aren't frozen until day 8, so this is instrument
development, not scoring):
    prompt template -> llama-server -> raw archive -> parser

Checks per model:
  1. server starts, model loads, /health green
  2. deterministic extraction on 2 known-fact sentences
  3. raw response archived BEFORE parsing (pre-reg hard rule)
  4. parser recovers >= 1 well-formed triple per sentence
  5. Qwen3: thinking disabled (and stripped if it leaks)
"""

from __future__ import annotations

import sys
from pathlib import Path

from llm_backend import MODELS, LlamaServer, RawArchive, response_text
from parse_outputs import parse_extraction

SENTENCES = [
    "Douglas Adams was born in Cambridge in 1952.",
    "Chennai is the capital of Tamil Nadu.",
]


def load_template() -> str:
    lines = Path("prompts/direct_extract.txt").read_text(encoding="utf-8").splitlines()
    return "\n".join(l for l in lines if not l.startswith("#")).strip()


def main() -> int:
    template = load_template()
    failures = []
    for key, spec in MODELS.items():
        print("=== %s ===" % key)
        archive = RawArchive("../outputs/selftest/%s.extract.jsonl" % key)
        try:
            with LlamaServer(spec) as server:
                for sent in SENTENCES:
                    messages = [{"role": "user",
                                 "content": template.format(sentence=sent)}]
                    resp = server.chat(messages, max_tokens=256)
                    archive.append(spec, messages, resp, meta={"sentence": sent,
                                                               "selftest": True})
                    parsed = parse_extraction(response_text(resp))
                    print("  %r" % sent)
                    for t in parsed.triples:
                        print("    -> %s | %s | %s" % t)
                    if parsed.had_think:
                        print("    [think block detected and stripped]")
                    if parsed.unparsed_lines:
                        print("    [unparsed: %r]" % parsed.unparsed_lines)
                    if not parsed.triples:
                        failures.append("%s: no triple from %r" % (key, sent))
        except Exception as e:
            failures.append("%s: %s" % (key, e))
            print("  ERROR: %s" % e)

    if failures:
        print("\nFAILURES:")
        for f in failures:
            print("  -", f)
        return 1
    print("\nLLM INSTRUMENT DRY RUN: ALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
