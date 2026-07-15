"""Experiment runner scaffold: languages x systems x arms.

Arms (PREREGISTRATION.md section 2):
  D (direct)   — source-language sentence -> extract -> canonicalize
  P (pivot)    — source sentence -> MT to English -> same English extract -> canonicalize
  E (english)  — XAlign English slice -> extract -> canonicalize (ceiling; unpaired)

TODO(day 3-8, after XAlign data lands):
  - data loader for reversed XAlign gold (data/xalign/, gitignored)
  - model backends: 2-3 open multilingual LLMs, 7-9B class, 4-bit (transformers +
    bitsandbytes or llama.cpp — decide on day 3 against available hardware)
  - MT backend for the pivot arm (candidate: IndicTrans2 or NLLB — VERIFY licenses
    and Indic coverage before wiring; do not cite from memory)
  - mREBEL baseline row (admin/mrebel-coverage.md: Hindi in-coverage anchor,
    7 languages out-of-coverage transfer test; day-8 keep/drop gate on schema mapping)
  - every raw generation saved verbatim to outputs/ before any parsing — the
    knows-it-but-can't-canonicalize probe (pre-registration B2 probe 2) scans these
  - synthetic-parallel robustness probe (pre-registration section 3): MT English gold
    items INTO each LR language, run arm D on them
  - MT quality-estimation scores logged per pivot translation (B2 probe 1;
    reference-free QE tool verified at implementation)

Hard rule: this file may not import or invoke any scoring until the pre-registration
commit (61f1ee1) is an ancestor of HEAD — enforced by convention and by the paper's
methods section, which cites the commit hash.
"""

LANGUAGES = ["hi", "bn", "te", "ta", "kn", "ml", "mr", "gu"]
CONTROL = "en"
ARMS = ["direct", "pivot", "english"]

if __name__ == "__main__":
    raise SystemExit("Scaffold only — see module docstring TODOs (data gate: day 3).")
