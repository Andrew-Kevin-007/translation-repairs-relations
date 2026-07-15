# Gold Audit Guidelines — Tamil slice (v1)

**Role in the study**: this is the measurement instrument for claim C2
(PREREGISTRATION.md row 7) and a released artifact ("how to add and verify a language").
It validates the central methodological move of the benchmark: reusing XAlign's
fact-to-text alignment gold as text-to-triple extraction gold.

**Scope**: the full Tamil manually-annotated test slice (656 items). Auditor: native
Tamil speaker. Target throughput: 60–90 items/day alongside other work (≈8–10 days,
fits days 3–12 of the plan; front-load — the audit gates nothing but feeds C2).

## Per-item procedure

For each item (Tamil sentence + gold triple set), record exactly one judgment per
gold triple and one completeness judgment per sentence:

1. **Read the sentence in Tamil first**, before looking at the gold triples
   (prevents anchoring on the gold).
2. **List every fact the sentence itself expresses** — only what a reader of this
   sentence alone can assert. World knowledge you happen to have does NOT count;
   if the sentence doesn't state it, it isn't in the sentence.
3. Compare with the gold triples and record per gold triple:
   - `GOLD-CORRECT` — the sentence expresses this fact.
   - `GOLD-WRONG` — the sentence does not express this fact (or contradicts it).
     Record why (e.g., alignment error, wrong entity, tense/negation missed).
4. Record per sentence:
   - `GOLD-INCOMPLETE` if step 2 found facts absent from gold. **Write each missing
     fact as a candidate triple** (surface forms + best-guess Wikidata property),
     then cross-check subject/object against Wikidata (QID lookup). Mark each
     missing fact `WD-CONFIRMED` / `WD-ABSENT`.

## Transliteration and entity-variant handling

- A Tamil surface form counts as expressing a gold entity if it is a standard
  rendering of that entity (direct script, transliteration, or established Tamil
  exonym). Record the surface form verbatim in every `GOLD-WRONG`/`GOLD-INCOMPLETE`
  entry — these become the transliteration-variance section of the error taxonomy.
- Honorifics, case suffixes, and sandhi-altered forms count as the base entity.
- If entity identity is genuinely ambiguous in the sentence alone, mark
  `AMBIGUOUS` (excluded from the miss-rate numerator and denominator, count reported).

## Single-auditor honesty protocol (until a second annotator exists)

- **Blind re-adjudication**: 10% of items (systematic sample: every 10th item) are
  re-audited by the same auditor ≥7 days after first pass, without sight of the
  first-pass judgments. Self-agreement (Cohen's kappa on the per-triple judgment)
  is reported in the paper. Disagreements with self are resolved by written rationale.
- Every non-`GOLD-CORRECT` judgment carries a one-line written rationale at audit
  time (rationales are released with the artifact).
- If a second annotator is recruited (open item): they audit the same 10% sample
  independently; inter-annotator kappa replaces self-agreement as the headline
  reliability figure.

## Decision rule (fixed in the pre-registration — do not tune)

- **Miss rate** = fraction of items marked `GOLD-INCOMPLETE` with at least one
  `WD-CONFIRMED` missing fact.
- C2 "understates precision" is claimed iff miss rate ≥ 5% AND the automated
  category-(ii) rate is positive in ≥7/8 languages (PREREGISTRATION.md row 7).
- Miss rate < 5% → the pre-registered inverse claim ("reliable reuse") is reported.
  Both outcomes are publishable; the audit cannot fail.

## Logging format

One CSV row per (item, gold-triple): `item_id, triple_idx, judgment, surface_subject,
surface_object, rationale`. One CSV row per missing fact: `item_id, MISSING,
candidate_triple, wd_status, rationale`. Files live in `data/audit/` (gitignored
until license clearance; released with the artifact after notification).
