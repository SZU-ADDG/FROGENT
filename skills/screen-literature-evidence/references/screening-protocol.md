# Screening and Memory Protocol

## Non-destructive record model

Maintain three linked objects:

1. Immutable raw artifact containing the provider response or document.
2. Normalized bibliographic record with provenance for every derived field.
3. Screening and extraction events that append decisions without overwriting history.

Normalization may repair casing, whitespace, identifier format, and date representation. Keep the original value and the transformation rule.

## Deduplication hierarchy

Use exact PMID, DOI, registry ID, patent ID, or accession ID first. Use title and author similarity only to form a review cluster. Verify study identity before merging records. One study may produce a protocol, primary report, subgroup report, long-term follow-up, correction, and retraction; keep their publication roles distinct.

## Controlled screening outcomes

- `include`: satisfies the current criteria and can proceed to extraction.
- `exclude`: fails a predefined criterion; require a reason code and explanation.
- `uncertain`: evidence is insufficient for a safe decision; require a resolution action.

Useful reason families include population, intervention or exposure, comparator, outcome, study design, publication type, date, language, duplicate role, unavailable content, retracted status, and out-of-scope mechanism.

## Quality and integrity checks

Check design fit, selection, measurement, confounding, attrition, selective reporting, multiplicity, statistical precision, data overlap, funding or conflict disclosures, correction history, retraction status, and applicability. Keep methodological quality separate from topical relevance.

## Memory admission gate

Admit a minimal claim excerpt only when it has:

- an included latest screening decision;
- a stable record identifier and raw artifact reference;
- a precise claim and source locator;
- study context and evidence direction;
- quality, indirectness, and limitation notes;
- an extraction or review timestamp.

Reconcile memory before every synthesis step. Remove an admitted evidence ID when a later full-text decision, correction, or retraction makes it ineligible. Preserve the earlier admission event in the audit ledger.
