---
name: screen-literature-evidence
description: Deduplicate, screen, quality-check, and admit biomedical evidence without deleting raw records or hiding exclusion reasons. Use after literature retrieval when records must be filtered safely for a review, evidence table, agent context, or local memory.
---

# Screen Literature Evidence

Apply reversible normalization and an explicit memory gate.

Read [screening-protocol.md](references/screening-protocol.md) before deduplicating related publications, excluding uncertain records, or admitting evidence to memory.

## Workflow

1. Freeze every raw response or full-text file as an artifact before cleaning.
2. Normalize fields into a derived record. Preserve the original title, abstract, identifiers, source payload, and retrieval timestamp.
3. Link duplicates using stable identifiers first, then conservative title, author, year, trial, cohort, and compound checks.
4. Keep corrections, retractions, protocols, conference abstracts, follow-ups, and subgroup reports linked to the study family instead of collapsing them blindly.
5. Screen metadata, abstract, and full text as separate stages. Record one decision and one or more controlled reasons at every stage.
6. Send ambiguous records to `uncertain`; resolve them through full text, a second check, or explicit adjudication.
7. Assess study design, population, comparators, endpoint validity, sample size, bias, confounding, missingness, multiplicity, reporting status, and applicability.
8. Extract claim-level evidence with a stable record ID, source locator, study context, direction, magnitude when available, and limitations.
9. Admit only qualified claim excerpts to working memory. Keep raw text, excluded records, and uncertain records in the evidence ledger.

## Loss controls

- Use soft flags for incomplete metadata, indirectness, preprint status, small samples, and low quality.
- Reserve hard exclusion for predefined criteria, confirmed duplication, unavailable decision-relevant content, or invalid records.
- Never impute missing results, dates, identifiers, populations, or methods.
- Preserve negative, null, and contradictory findings.
- Re-run screening from the ledger when criteria change.

## Output

Return deduplication clusters, stage-level flow counts, included records, excluded records with reasons, uncertain records and resolution needs, quality assessments, admitted evidence IDs, and records withheld from memory.
