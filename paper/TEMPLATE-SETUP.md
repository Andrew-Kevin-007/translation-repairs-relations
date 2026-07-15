# Springer CCIS template setup (verified 2026-07-15)

CCIS papers follow the **LNCS author instructions** — Springer's conference-proceedings
guidelines state CCIS uses the same LaTeX class and formatting rules as LNCS
(`llncs.cls`). Sources checked this session:

- CCIS series home: https://link.springer.com/series/7899
- Springer conference proceedings guidelines (templates + Instructions for Authors PDF):
  https://www.springer.com/gp/computer-science/lncs/conference-proceedings-guidelines
- Overleaf-hosted official template ("Springer Lecture Notes in Computer Science"):
  https://www.overleaf.com/latex/templates/springer-lecture-notes-in-computer-science/kzwwpvhwnvfj

## Setup (choose one)

**Option A — Overleaf (recommended: zero local LaTeX install, compiles today):**
1. Open the Overleaf template link above → "Open as Template".
2. Replace the body with `main.tex` from this directory (keep the template's `llncs.cls`).
3. Compile once TODAY — Gate: a compiling skeleton is a day-1 exit criterion.

**Option B — local:** download the LaTeX2e Proceedings Template ZIP from the Springer
guidelines page; `main.tex` here assumes `llncs.cls` is on the path.

## Compliance checklist (from the SPELLL 2026 CFP + Springer policy)

- [ ] Regular paper: 12–16 pages CCIS format (short: 6–8) — page budget tracked per section in main.tex
- [ ] **Double-blind**: no names, no affiliation, no acknowledgments, anonymized artifact link,
      self-citations in third person
- [ ] Springer Nature AI-disclosure statement (drafted at writing time, day 13+)
- [ ] Submission via OpenReview (account created — user-side action, day 1)
- [ ] Submit Aug 1–2, never Aug 3
