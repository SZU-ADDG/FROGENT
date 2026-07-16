---
name: synthesize-biomedical-evidence
description: Synthesize screened biomedical studies into claim-level conclusions with direct evidence, counterevidence, confidence, temporal validity, and citation provenance. Use after screening for target, mechanism, efficacy, safety, biomarker, preclinical, clinical, or translational conclusions.
---

# Synthesize Biomedical Evidence

Build conclusions from admitted evidence IDs and retain disagreement.

Read [evidence-model.md](references/evidence-model.md) before grading confidence, reconciling conflicts, or writing a decision summary.

## Workflow

1. Restate each decision-relevant proposition as a precise claim with population, biological context, intervention or exposure, comparator, outcome, and time horizon. Identify whether the question asks for one source study's conclusion or the current field-level conclusion.
2. Build a claim-evidence matrix using currently admitted evidence IDs. Keep supportive, null, contradictory, and indirect evidence in separate columns.
3. Group multiple publications from the same study or cohort to prevent double counting.
4. Compare design, population, target definition, intervention, dose, model, endpoint, follow-up, analysis, and publication status before treating results as comparable.
5. Explain heterogeneity and contradictions. Distinguish biological differences, methodological differences, temporal changes, statistical uncertainty, and unresolved conflict.
6. Judge confidence from design fit, quality, consistency, directness, precision, integrity, and recency. Keep the rationale visible.
7. Run sensitivity checks that remove high-bias, indirect, preprint-only, retracted, or duplicated evidence.
8. Surface unavailable databases, OA failures, abstract-only records, reader failures, and unresolved verification as explicit coverage gaps.
9. Date every conclusion with an exact `as_of` value and identify verified authors, institutions, corrections, or study families that need future monitoring.

## Verdict calibration

- When a question targets a named or clearly retrievable source study, answer that study's conclusion first. Put later replications, corrections, alternative diagnoses, and current-field updates in a separate paragraph.
- Do not map every numerical difference to `yes`. Check the authors' stated conclusion, uncertainty or statistical support, effect size, and decision relevance. A small or unsupported difference may still support `no meaningful difference` or `maybe`.
- For a yes/no source-title question, follow the conclusion's qualitative polarity. Wording such as `only slight`, `similar`, or `no meaningful difference` maps to `no` while the numeric difference remains visible in the explanation.
- If source-study and current-field answers differ, return both labels explicitly and explain why; never silently replace the original study answer with later evidence.

## Synthesis rules

- Cite the primary record for a primary claim; use reviews to map the field and locate sources.
- Keep absence of evidence separate from evidence supporting no effect.
- Keep statistical significance separate from effect size and decision relevance.
- Carry species, model, assay, population, and endpoint boundaries into the claim wording.
- Avoid a single confidence score that hides incompatible evidence dimensions.
- Never promote a raw abstract, search snippet, or unscreened tool output into a conclusion.
- Never cite an unverified model-memory candidate, failed reader output, or evidence revoked by a later integrity decision.

## Output

Return a claim-evidence matrix, concise narrative synthesis, counterevidence, confidence by claim, sensitivity results, temporal validity, unresolved questions, and the evidence IDs supporting every material sentence.
