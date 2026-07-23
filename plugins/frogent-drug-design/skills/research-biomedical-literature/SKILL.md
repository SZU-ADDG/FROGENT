---
name: research-biomedical-literature
description: Conduct an end-to-end, traceable biomedical literature review with explicit search dates, screening decisions, evidence quality, contradictions, and memory controls. Use for disease, target, mechanism, drug, biomarker, preclinical, clinical, safety, or translational research questions that require evidence rather than a quick factual lookup.
---

# Research Biomedical Literature

Run literature work as an evidence pipeline with auditable stage boundaries.

Read [provider-routing.md](references/provider-routing.md) before selecting live databases, OA fallbacks, or author-network expansion.

## Establish the review contract

Record the decision question, intended use, population or biological system, intervention or exposure, comparator, outcomes, acceptable evidence types, language limits, date range, and exact `as_of` date. Mark unknown fields and ask only for information that changes the search or inclusion criteria.

## Execute the pipeline

1. Use `$plan-literature-search` to create explicit source-query pairs, retrieval waves, inclusion criteria, and stop rules.
2. Convert model memory into `KnowledgeCandidate` seeds. Mark every title, identifier, author, lab, and claim unverified until a database lookup confirms it.
3. Route core retrieval through Europe PMC and PubMed. Save each query, source, execution time, result count, and raw response before normalization.
4. Resolve OA full text when available; retain an abstract-only path and coverage gap when OA retrieval fails.
5. Group records into paper or study families, then delegate bounded reader tasks. Accept only structured claim-level reports and isolate failed or malformed readers.
6. Use `$screen-literature-evidence` to deduplicate, assess integrity and quality, and control memory admission.
7. Expand through citations, linked trials, verified authors or institutions, and new terminology. Treat author reputation only as retrieval priority.
8. Use `$synthesize-biomedical-evidence` to build conclusions from admitted evidence with counterevidence, uncertainty, and tool coverage gaps.
9. Checkpoint completed queries and resume without repeating them. Reconcile memory after corrections, retractions, or changed screening decisions.
10. When the user asks what molecule, target, route, or experiment to prioritize, hand the admitted evidence IDs and preserved counterevidence to `$prioritize-design-hypotheses`. Keep evidence strength unchanged while the Agent adds an explicitly labeled qualitative decision layer.

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
