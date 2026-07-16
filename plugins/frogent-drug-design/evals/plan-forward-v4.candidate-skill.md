---
name: plan-literature-search
description: Build reproducible biomedical literature search strategies with source routing, concept blocks, query waves, temporal cutoffs, recall checks, and explicit stop rules. Use before evidence retrieval for systematic, scoping, rapid, target, mechanism, drug, safety, clinical, or translational questions.
---

# Plan Literature Search

Design a search that can be inspected, replayed, and updated.

Read [query-strategy.md](references/query-strategy.md) when choosing sources, expanding concepts, or defining retrieval waves.

## Workflow

1. Convert the decision question into a suitable frame: PICO, PECO, target-mechanism, biomarker, safety, or translational.
2. Define the exact `as_of` date, publication range, evidence types, organisms, languages, and decision-relevant outcomes.
3. Build concept blocks for diseases, targets, pathways, drugs, aliases, identifiers, interventions, outcomes, and study designs.
4. Combine controlled vocabulary with title, abstract, identifier, and free-text synonyms. Preserve every exact query string.
5. Route each evidence type to appropriate primary, trial, regulatory, preprint, citation-graph, and patent sources that are available.
6. Run a sentinel query and verify that known anchor records are recovered. Expand missing aliases before broad retrieval.
7. Plan broad discovery, focused confirmation, citation expansion, and temporal-update waves separately.
8. Define inclusion, exclusion, deduplication, escalation, and stopping rules before screening begins.

## Recall and precision controls

- Avoid aggressive `NOT` clauses unless a pilot confirms that they preserve anchor records.
- Keep mechanism and efficacy questions in separate query branches when one branch suppresses the other.
- Include null, negative, replication, correction, and retraction searches for high-impact claims.
- Record unavailable sources as coverage gaps.
- Construct each decision-critical anchor or counterevidence checkpoint as one route-specific locator-first query: (an exact PMID, DOI, NCT number, regulatory-document locator, exact title, or exact study name) OR (a minimal branch containing one alias for every essential entity and event). Keep the locator branch free of author, year, outcome, assay, and other AND filters, and never invent a locator. Preserve the query cap and the existing route and wave coverage.
- Treat result count changes as database-version observations, not proof that the query changed.

## Output

Return a versioned search plan containing the question frame, source map, concept dictionary, exact queries, `as_of` date, retrieval order, expected evidence types, anchor-record checks, inclusion and exclusion criteria, and stop rules.
