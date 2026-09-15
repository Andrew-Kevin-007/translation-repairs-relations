# xlkg — Cross-Lingual Knowledge Graph Population from Low-Resource Text

Hypothesis-driven study of where the low-resource penalty in populating Wikidata
from text actually lives: relation understanding or entity canonicalization.

Accepted at SPELLL 2026, Track 7, for publication by Springer in CCIS.

**Start here: [PREREGISTRATION.md](PREREGISTRATION.md)** — the hypothesis, decision
thresholds, and statistical procedures were committed before any model output was
scored (first commit of this repository, `61f1ee1`, 2026-07-15). `score.py` checks
that commit against git history itself and refuses to run if it is not an ancestor
of HEAD — the constraint is enforced by the tool, not just stated in prose.

## Layout

- `PREREGISTRATION.md` — frozen hypothesis + decision table (amendment log at bottom)
- `src/` — evaluation harness: component metrics (relation/entity/triple F1),
  hierarchical bootstrap, three-way Wikidata triple classification, prompt templates
- `audit/` — native-speaker gold-audit protocol (benchmark reliability instrument)
- `paper/` — manuscript source (Springer CCIS / LNCS format). The compiled PDF is
  not included here; it is a build artifact of `main.tex` plus `llncs.cls`.
- `data/` — gold data (gitignored; released only under XAlign's upstream license)

## Reproducing

The harness has two moving parts with separate dependencies:

- The Wikidata client, metrics, bootstrap, and scoring run in a standard Python
  environment (see the imports in `src/`).
- The pivot arm's translation step runs local IndicTrans2 models and has its own
  pinned environment: `src/requirements-mt.txt`.

`src/run_matrix.py` is the experiment runner (languages x systems x arms); `score.py`
does the scoring and will not run ahead of the pre-registration commit. Full local
model inference (GGUF, via llama.cpp) is required to regenerate raw outputs from
scratch; the parsed results and figures in the paper were produced this way.

## Adding a language

The harness is language-agnostic: a new language needs (1) gold triples aligned to
sentences, (2) an MT route to English for the pivot arm, (3) optionally a native
audit pass per `audit/`. See `src/run_matrix.py`.

## License

The evaluation harness and tooling in `src/` are released under the MIT License
(see `LICENSE`). The paper manuscript is not covered by that license; its rights
follow the publication agreement with Springer.
