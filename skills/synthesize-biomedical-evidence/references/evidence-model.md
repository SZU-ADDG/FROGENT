# Claim-Level Evidence Model

## Claim schema

Each claim should contain:

- claim ID and precise statement;
- biological or clinical context;
- supporting evidence IDs;
- counterevidence IDs;
- study-family links to prevent double counting;
- confidence dimensions;
- limitations and applicability boundary;
- exact `as_of` date.

## Confidence dimensions

Assess dimensions separately before assigning a plain-language summary:

1. Design fit for the claim.
2. Risk of bias and research integrity.
3. Directness to the target population, model, intervention, and outcome.
4. Consistency across independent study families.
5. Precision and sample information.
6. Effect magnitude and decision relevance.
7. Publication, correction, retraction, and regulatory status.
8. Recency relative to the decision.

Use `high`, `moderate`, `low`, or `unassessed` only with a written rationale. A stronger design can still provide indirect evidence; a lower-level design can still expose a meaningful safety signal.

## Conflict handling

Classify conflicts as population, model, intervention, dose, endpoint, timing, analysis, quality, or unexplained. Prefer a scoped claim that represents the boundary of agreement. Keep credible counterevidence attached even when one interpretation is favored.

## Citation integrity

Trace every material statement to stable identifiers and source locators. Do not transfer a claim from a review citation to a primary paper without checking the primary paper. Mark conference abstracts, preprints, secondary analyses, subgroup reports, and regulatory summaries explicitly.

## Memory payload

Working memory receives concise qualified excerpts and claim objects. Raw documents, complete abstracts, search snippets, excluded records, and provider payloads remain in the artifact store and evidence ledger. Reconcile admitted IDs after new full text, corrections, retractions, or criteria changes.
