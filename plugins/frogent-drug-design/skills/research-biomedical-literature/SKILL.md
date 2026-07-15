---
name: research-biomedical-literature
description: Conduct an end-to-end, traceable biomedical literature review with explicit search dates, screening decisions, evidence quality, contradictions, and memory controls. Use for disease, target, mechanism, drug, biomarker, preclinical, clinical, safety, or translational research questions that require evidence rather than a quick factual lookup.
---

# Research Biomedical Literature

Run literature work as an evidence pipeline with auditable stage boundaries.

## Establish the review contract

Record the decision question, intended use, population or biological system, intervention or exposure, comparator, outcomes, acceptable evidence types, language limits, date range, and exact `as_of` date. Mark unknown fields and ask only for information that changes the search or inclusion criteria.

## Execute the pipeline

1. Use `$plan-literature-search` to create the source map, query set, retrieval waves, inclusion criteria, and stop rules.
2. Save each query, source, execution time, result count, and raw response before normalization.
3. Retrieve broad metadata first, then fetch abstracts and full text only for records that need them.
4. Use `$screen-literature-evidence` to deduplicate, screen, assess quality, and control memory admission.
5. Expand through backward citations, forward citations, author or trial links, and key terminology discovered during screening. Record each expansion as a new query wave.
6. Use `$synthesize-biomedical-evidence` to build claim-level conclusions, counterevidence, uncertainty, and evidence gaps.
7. Re-run the search near delivery when the task requires current evidence and the original search time is stale for the decision.

## Keep four evidence layers

1. **Raw records**: immutable retrieval payloads and files.
2. **Screening ledger**: every inclusion, exclusion, duplicate link, uncertainty flag, and reason.
3. **Qualified evidence**: claim excerpts with stable identifiers, source locators, study context, quality notes, and limitations.
4. **Synthesis**: conclusions linked only to qualified evidence and explicit counterevidence.

Keep raw, excluded, and uncertain material outside working memory. Preserve it in the ledger so criteria changes can be replayed without searching from scratch.

## Deliverables

Return the review question and `as_of` date, exact search log, flow counts, screened-study table, claim-evidence matrix, contradictions, confidence judgments, excluded-but-near-miss records, and unresolved gaps. Label preprints, corrected or retracted work, secondary sources, non-human evidence, and indirect evidence.

## Stop conditions

Stop when the planned sources and citation waves are complete, two consecutive expansion waves add no decision-relevant evidence, or the agreed budget is exhausted. State which condition ended the review. Never describe a budget-limited search as exhaustive.
