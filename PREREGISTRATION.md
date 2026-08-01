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

(any post-data change to rules or thresholds must be appended here with date, reason, and impact statement; the sections above are never edited)

### Amendment 1 — 2026-07-17 (PRE-SCORING): decision-table statistical repairs

**Timing statement**: recorded before any model output was scored. The
extraction matrix (run_matrix.py, run-id main-v1) began generating on
2026-07-17; score.py — the only component that computes metrics, and which is
git-gated on this file's history — has never been executed. No F1, GRR, or any
experimental quantity has been observed by anyone.

**Reason**: an internal adversarial review (2026-07-17) found the frozen
consistency criterion arithmetically unsatisfiable as written, plus three
under-specified rules. These are repairs of internal inconsistency, not
retuning: no threshold moves in a direction that makes any claim easier
relative to a satisfiable reading of the frozen text.

**A1 — Sign-test sidedness.** §5 requires "exact two-sided binomial sign test
... ≥7/8 in the same direction (p < 0.05)". For n=8, k=7 the exact two-sided
p = 0.0703 > 0.05; only 8/8 (p = 0.0078) satisfies the two-sided reading, so
the frozen "≥7/8" threshold and the two-sided test contradict each other.
Resolution: the test is declared **one-sided** in the direction pre-specified
by H1 (each row's rule already names its direction of repair/improvement).
Under the one-sided test, 7/8 gives exact p = 0.0352 < 0.05 — the frozen
"≥7/8" operating point becomes coherent. Justification: H1 is directional;
a two-sided consistency test was an error of transcription, as evidenced by
the impossible threshold pair. Impact: makes the criterion satisfiable as the
frozen threshold intended; does not lower the bar below any satisfiable
reading of the frozen text (the only stricter coherent alternative, 8/8
two-sided, is equivalent to 8/8 one-sided at p = 0.0039, and remains
reportable from published per-language directions).

**A2 — Consistency rule under exclusion-reduced n.** §3's 8-point-gap
exclusion can reduce the usable-language count below 8; the frozen "≥7/8" is
then undefined. General rule: with n usable languages, consistency requires
**all-but-at-most-one in the H1 direction AND exact one-sided binomial
p < 0.05 given n**. Numerically: n ≥ 8 → (n−1) suffices; n ∈ {5,6,7} →
all n must agree (at n=7, 6/7 gives p = 0.0625; 7/7 gives p = 0.0078);
n < 5 already triggers §3's escape hatch (underpowered, CIs without verdict).

**A3 — Holm-Bonferroni family size.** §5 hardcodes "6 primary-family tests
(2 metrics x 3 systems)" while §2 specifies "2-3 open multilingual LLMs". The
family is defined as **2 metrics × N systems actually run**. The matrix
launched 2026-07-17 runs N=2 (Qwen3-8B, Llama-3.1-8B, both Q4_K_M) → family
size 4. Fixed here, before any p-value exists.

**A4 — "Majority across systems" at N=2.** Undefined as frozen. Definition:
at N=2, "majority" means **unanimity**; if the two systems disagree on a
row's three-way verdict, that row is scored at the weaker of the two outcomes
(REPAIRED+PARTIAL → PARTIAL; any+NOT-REPAIRED → NOT REPAIRED), and row 4
routes accordingly (typically to MIXED). This is the conservative resolution:
disagreement can only weaken, never strengthen, a claim.

Amendments drafted with AI assistance (disclosed per the paper's
AI-assistance statement); arithmetic verified independently by direct
computation before recording.

## Amendment 2 (2026-07-20, at first scoring, before any re-parse or re-score)

**A5 — Stage-2 format-echo leniency (mechanical parser completion).** The
frozen parser (`src/parse_outputs.py`) declares, in its frozen rule list:
"format ECHOES ignored (not triples, not unparsed): a line that merely
repeats the template header" — motivated by the 2026-07-17 dry-run finding
that Llama-3.1 echoes format headers before answering. The implementation,
however, only encoded the stage-1 header tuple ("subject | relation |
object"); the stage-2 template line ("subject_qid | property_pid |
object_qid_or_literal", `src/prompts/canonicalize.txt`) was not encoded.
Because `parse_canonicalization` takes the first 3-field line, every stage-2
response that echoes the header parses to the placeholder row instead of the
model's answer on the following line.

Discovered at first scoring (2026-07-20): Llama-3.1-8B echoed the stage-2
header in 23,280 / 24,041 canonicalization responses (96.8%); in 22,698 of
those, well-formed IDs follow immediately after the echoed header; 582 are
header-only (genuinely unparseable and remain so). Qwen3-8B echoed it in 0
responses, so the rule provably cannot alter Qwen results.

Resolution: the stage-2 header tuple is added to the format-echo skip — an
implementation completion of the already-frozen leniency, not a new rule.
It is content-neutral (defined entirely by our own template string), decided
from artifact inspection of the raw archives (not from which results it
produces), and applied uniformly to both systems. Execution discipline:
re-parse strictly from the frozen raw archives (`outputs/raw/*.canon.jsonl`;
no model is re-run; extraction stage untouched) into a NEW results file
(`outputs/parsed/main-v1r.jsonl`); the original parse
(`outputs/parsed/main-v1.jsonl`) and its scored report are preserved
unmodified, and the paper will disclose pre-fix Llama numbers alongside
post-fix. This amendment is committed before the re-parse is executed.

## Amendment 3 (2026-08-01, recording 2026-07-31 retrospectively; before the completion sample is drawn)

**A6 — Tamil native-speaker audit: executed procedure and pre-specified
completion sample.** The frozen protocol — `audit/tamil-audit-guidelines.md`
and row 7 of the decision table — specifies a native-speaker audit of the
full Tamil manually-annotated test slice, per item, covering the 601
retained items (656 source; see Table 1).

That is not what was executed. Under the SPELLL 2026 submission-deadline
constraint (hard deadline 2026-08-03 AoE), the full per-item audit was not
performed. In its place: (a) an automatic candidate screen was run over all
601 retained items, proposing, per item, relations the sentence may assert
that the gold lacks; (b) the screen surfaced 25 items as candidate
gold-incompleteness cases; (c) a native Tamil speaker adjudicated all 25
individually on 2026-07-31, judging for each whether the sentence itself
asserts the candidate fact. Steps (a)-(c) were executed before this
amendment was written; the amendment records them retrospectively, and
they are not presented here as pre-registered.

Of the 25 adjudicated items, the screen's own verdicts split 11 positive
and 14 negative. The adjudicator upheld all 11 positives (screen precision
11/11 on its own positive verdicts) and, on review of the 14 negatives,
overturned 3 to positive: `ta-test-0031` (employer), `ta-test-0269`
(employer), and `ta-test-0585` (country of citizenship). Across the 25
adjudicated items this yields 14 true positives in total, of which the
screen itself had caught 11 — screen recall of 11/14 on adjudicated items,
a measured false-negative rate of approximately 21%. Adjudicated
gold-incomplete items: 14 of 601 (2.33%).

The remaining 576 items were marked not-incomplete by the automatic screen
and were never individually reviewed. Because the screen's measured
false-negative rate is nonzero, 14/601 is a lower bound on the true miss
rate, not an estimate of it, and the row-7 5% threshold determination is
not licensed on this figure alone. Reaching the 5% threshold would require
16 further misses among the 576, a rate of about 2.8%.

The only prospective element of this amendment is the following. A random
sample of N = 100 items, drawn without replacement from the 576
unadjudicated items, will be judged by the same native speaker under the
same criterion, to estimate the screen's false-negative rate on unflagged
items. Draw procedure, fixed here for reproducibility: take the 576
item_ids not among the 25 adjudicated, sort them lexicographically, and
select with Python `random.Random(20260731).sample(sorted_ids, 100)` —
seed 20260731.

The completion estimate is (14 + misses projected from the 100-item sample
onto the remaining 576) / 601, reported with an interval. **The frozen 5%
threshold and the row-7 C2 outcome mapping are not modified by this
amendment**: at or above 5% supports the claim that generation-oriented
gold understates extraction precision (§8, C2); below 5% licenses the
pre-registered inverse claim, reliable reuse. The paper will report
whichever way the completed estimate falls, and will describe the audit as
it was actually run — automatic candidate screening plus native-speaker
adjudication of the screened items and of a sampled completion check — not
as a full per-item native-speaker audit.

Execution discipline: this amendment is committed before the 100-item
completion sample is drawn and judged.

This amendment was drafted with AI assistance (disclosed per the paper's
AI-assistance statement); the reported counts and rates were checked for
arithmetic consistency before recording.
