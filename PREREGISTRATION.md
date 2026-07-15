# PRE-REGISTRATION — Cross-Lingual Knowledge Graph Population Study (xlkg)

**Status**: FROZEN at first commit. Any later change is an AMENDMENT appended to the log at the bottom; the original text is never edited.
**Date frozen**: 2026-07-15 (19 days before the SPELLL 2026 submission deadline, 2026-08-03 AoE).
**Rule that gives this file meaning**: this commit exists BEFORE any model output is scored. All decision thresholds, statistical procedures, and verdict mappings below were fixed without sight of any experimental result.

---

## 1. Primary hypothesis (H1)

**Formal claim under test:**

> "The low-resource penalty in populating Wikidata from Indic-language text lies in entity canonicalization, not relation understanding: under the pre-registered criterion below, English translation repairs relation identification (GRR >= 0.75 with residual gap within the 95% noise band) but not entity grounding (GRR < 0.35, or a statistically significant residual gap with GRR difference >= 0.30)."

Prose form for the abstract (rule footnoted): "Translating the input to English repairs relation identification but not entity grounding" — per the gap-recovery criterion in this document.

## 2. Design summary

- **Languages**: target 8 Indic languages — Hindi, Bengali, Telugu, Tamil, Kannada, Malayalam, Marathi, Gujarati — plus English control. Gold source: manually annotated XAlign test splits (Abhishek et al., WWW Companion 2022), reversed from fact-to-text alignment into text-to-triple extraction gold.
- **Arms**: (D) DIRECT — extraction from original-language text; (P) PIVOT — machine translation to English, then the same English extraction pipeline; (E) ENGLISH CONTROL — extraction from the XAlign English slice.
- **Systems**: 2-3 open multilingual LLMs (7-9B class, 4-bit quantized, zero- and few-shot, extract-then-canonicalize prompting); mREBEL as supervised baseline (secondary C3, gated day 8); optional model-size sweep for exploratory C5-fragment.
- **Metrics per run**: relation-F1 (property only), entity-F1 (subject/object QIDs only), full-triple F1; strict (Wikidata-ID) and relaxed (surface) variants.
- **Three-way prediction classification**: every predicted triple is classified (i) in gold; (ii) not in gold but verifiably true in Wikidata (gold incompleteness); (iii) absent from Wikidata (candidate hallucination).

## 3. Definitions

**Gap Recovery Ratio.** For metric m in {relation-F1, entity-F1}, per (language, system):

    GRR_m = (m_pivot - m_direct) / (m_english - m_direct)

Report unclipped and clipped-to-[0,1].

**Cell exclusion (underpowered gap)**: cells with baseline gap (m_english - m_direct) < 8 F1 points are excluded from GRR verdicts (logged, reported).

**Escape hatch**: if a metric has fewer than 5 usable languages after exclusion, GRR verdicts for that metric are declared underpowered; CIs are reported without a verdict.

**English-ceiling pairing note (pre-empted reviewer attack)**: the English ceiling uses XAlign's English slice — different sentences from the LR items, same domain/register. pivot-direct is item-paired; the English term is unpaired. CI treatment: hierarchical bootstrap (independent item resampling per set, 10,000 resamples). **Pre-registered robustness probe**: machine-translate a sample of English gold items INTO each LR language, run the direct arm on this synthetic-parallel text against the same gold — a fully paired denominator check (translationese caveat stated).

## 4. Decision table

| # | Quantity | Rule | Statistics | Verdict contribution |
|---|---|---|---|---|
| 1 | Relation-F1 repair | REPAIRED: GRR >= 0.75 AND residual (english - pivot) CI includes 0. PARTIAL: 0.35 <= GRR < 0.75 AND (pivot - direct) CI excludes 0. NOT REPAIRED: GRR < 0.35 OR improvement CI includes 0 | 95% hierarchical bootstrap per cell; cross-language exact sign test (>=7/8 same direction, p<0.05); majority across systems; Holm-Bonferroni over the 6 primary-family tests (2 metrics x 3 systems) | H1 needs REPAIRED here |
| 2 | Entity-F1 repair | Same three-way rule | Same | H1 needs NOT REPAIRED (or PARTIAL, see row 3) here |
| 3 | Asymmetry | GRR_rel - GRR_ent >= 0.30 with bootstrap CI on the difference excluding 0 | Same bootstrap | Required for H1 CONFIRMED when row 2 is PARTIAL rather than NOT REPAIRED |
| 4 | Verdict map | H1 CONFIRMED: row1 REPAIRED + row2 NOT-REPAIRED/PARTIAL + row3 pass. B2: rows 1 and 2 both REPAIRED. B3: row 1 NOT REPAIRED. MIXED: anything else -> report GRR profile, lead with C2 | — | Every branch has a designated headline |
| 5 | B2 strong form | Zero cells where direct significantly beats pivot | Per-cell 95% paired CI | Licenses the B2 claim sentence; otherwise weaker asymmetric form |
| 6 | B3 coverage decomposition | Bottom-vs-top popularity-quartile error ratio >= 1.5 in pivot arm AND >= 50% residual-gap shrinkage on exclusion | Bootstrap on ratio and shrinkage | Licenses the B3 claim sentence |
| 7 | C2 gold reliability | "Understates" claimed iff Tamil-audit miss rate >= 5% of items AND automated category-(ii) rate positive in >= 7/8 languages; < 5% -> pre-registered inverse claim ("reliable reuse") | Audit count + sign test | Always reported |
| 8 | C3 inversion | mREBEL macro-F1 below best zero-shot LLM with non-overlapping 95% CIs in >= 5/8 languages | Per-language CIs | Secondary; day-8 gate |
| 9 | C4 fertility (exploratory) | \|Spearman rho_fertility\| > \|rho_resource\| with bootstrap CI on delta-rho excluding 0 | Uncorrected, labeled exploratory | Never a verdict |
| 10 | C5 fragment (exploratory) | "Stable ordering" iff Kendall tau >= 0.7 across the size sweep with CI excluding 0 | Uncorrected, labeled | Never a verdict |

## 5. Statistical procedures

- **Bootstrap**: hierarchical/paired bootstrap, 10,000 resamples, 95% CIs. Item-level pairing for pivot-vs-direct (same input items); independent resampling for the unpaired English term.
- **Cross-language consistency**: exact two-sided binomial sign test across the 8 languages; consistency requires >= 7/8 in the same direction (p < 0.05).
- **Multiple comparisons**: Holm-Bonferroni across the 6 primary-family tests (2 metrics x 3 systems). Secondary/exploratory analyses (rows 8-10) uncorrected and labeled as such.
- **"Significant" anywhere in the paper** = 95% CI excluding 0 under the stated bootstrap, Holm-corrected within the primary family.

## 6. Threshold justification (fixed before data)

With 500-800 gold items per language, the F1 bootstrap CI half-width runs roughly 2-4 points. If baseline gaps land in the 15-25-point range that the low-resource literature pattern suggests, a residual of 25% of the gap (4-6 points) is the smallest residual reliably distinguishable from measurement noise — hence REPAIRED demands recovery to within that noise band (GRR >= 0.75 plus the residual-CI condition, so the threshold never acts alone). The 0.35 floor requires movement of roughly twice the noise band relative to expected gaps — below it, "improvement" is indistinguishable from resampling jitter. The C2 5% floor is likewise noise-anchored: a smaller precision distortion cannot be separated from the CI half-width at our n. All thresholds are interpretive conventions fixed before data; continuous GRR values are always published so readers can apply their own cutoffs.

## 7. Falsification-branch claims (pre-registered second-order insights)

**Branch B2 (pivot repairs BOTH metrics — H1 dies):**

> "Multilingual pretraining provides no measurable language-native access to structured knowledge in current open LLMs: an explicit external translation step matches or exceeds direct reading of the source language on every component of the KG-population task, implying the models' usable knowledge interface is English-bound."

"No measurable" = zero (language, system, metric) cells in which the direct arm significantly beats the pivot arm (row 5). One robust counterexample cell breaks the strong form; the weaker asymmetric form is then reported.
Sharpening measurements (zero-cost, from collected data): (1) correlate pivot-arm residual per-language error with reference-free MT quality-estimation scores — residual tracking QE = "the low-resource gap has reduced to the MT gap"; residual uncorrelated = irreducible non-MT residual, identified in the taxonomy; (2) knows-it-but-can't-canonicalize probe — string-scan direct-arm failures for the gold entity's English/Wikidata label or transliteration; (3) interface-strength probe — few-shot direct vs zero-shot pivot.

**Branch B3 (pivot fails even on relation-F1):**

> "A defined fraction of the apparent language gap in KG population is an entity-coverage gap, not a language gap: extraction fails on locally prominent but globally tail entities at comparable rates whether the model reads the original language or an English translation."

Licensed only by row 6: stratify all arms by entity popularity (Wikidata sitelink count); require (i) bottom-quartile entities show >= 1.5x the error rate of top-quartile entities within the pivot arm, and (ii) excluding bottom-quartile entities shrinks the residual pivot-vs-English gap by >= 50%. Otherwise report the stratification and attribute failure to translation distortion (checked against the QE correlation, computed in every branch).

## 8. Secondary claims (fixed identities)

- **C2 (mandatory)**: reusing generation-oriented alignment gold as extraction gold understates model precision (rule: row 7; Tamil native audit + automated category-(ii) rates; inverse claim pre-registered if < 5%).
- **C3 (gated day 8)**: the documented advantage of supervised multilingual relation extractors over LLMs (high-resource regime) inverts on languages outside the supervised model's training coverage (rule: row 8). Coverage fact fixed pre-data: SREDFM/mREBEL covers Hindi but none of our other 7 languages (verified 2026-07-15; see admin/mrebel-coverage.md) — Hindi is the in-coverage anchor; the other 7 constitute the transfer test.
- **C4 (exploratory)**: tokenizer fertility vs resource proxies as degradation predictor (rule: row 9).
- **C5-fragment (exploratory)**: per-language degradation ordering stable across model scale (rule: row 10).
- **C6**: relation-hallucination structure — taxonomy dimension only, never a claim.

## 9. Banned vocabulary

"Largely", "most", "significantly" (unless per Section 5), "systematically" (unless per row 7), "dramatically", "broken" — results text states point estimates with CIs.

## 10. Amendment log

(empty — any post-data change to rules or thresholds must be appended here with date, reason, and impact statement; the sections above are never edited)
