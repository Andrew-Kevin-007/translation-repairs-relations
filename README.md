# xlkg — Cross-Lingual Knowledge Graph Population from Low-Resource Text

Hypothesis-driven study of where the low-resource penalty in populating Wikidata
from text actually lives: relation understanding or entity canonicalization.

**Start here: [PREREGISTRATION.md](PREREGISTRATION.md)** — the hypothesis, decision
thresholds, and statistical procedures were committed before any model output was
scored (first commit of this repository).

## Layout

- `PREREGISTRATION.md` — frozen hypothesis + decision table (amendment log at bottom)
- `src/` — evaluation harness: component metrics (relation/entity/triple F1),
  hierarchical bootstrap, three-way Wikidata triple classification, prompt templates
- `audit/` — native-speaker gold-audit protocol (benchmark reliability instrument)
- `paper/` — manuscript (Springer CCIS format)
- `admin/` — project logistics (not part of the released artifact)
- `data/` — gold data (gitignored; upstream license/permission applies)

## Adding a language

The harness is language-agnostic: a new language needs (1) gold triples aligned to
sentences, (2) an MT route to English for the pivot arm, (3) optionally a native
audit pass per `audit/`. See `src/run_matrix.py`.

*(Repository anonymized for double-blind review.)*
