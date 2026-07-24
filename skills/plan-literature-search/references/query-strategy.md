# Biomedical Query Strategy

## Source routing

| Evidence need | Preferred source class | Main control |
|---|---|---|
| Peer-reviewed biomedical studies | MEDLINE/PubMed and available subject indexes | Controlled vocabulary plus free text |
| Registered or ongoing trials | Trial registries | Match registry IDs to publications |
| Regulatory status and safety actions | Regulator databases and labels | Preserve jurisdiction and effective date |
| Recent unreviewed findings | Preprint servers | Carry preprint status into every claim |
| Citation expansion and metadata | Citation graphs and DOI metadata services | Verify claims against primary records |
| Chemistry and prior art | Patent and chemistry sources | Separate legal status from scientific evidence |

Use more than one source class when a decision spans discovery, validation, clinical translation, and safety. Record sources that are unavailable.

## Concept construction

- Expand gene and protein symbols, previous names, family names, accession IDs, and species variants.
- Expand drugs with generic names, brand names, development codes, salt forms, metabolites, and common misspellings.
- Expand diseases with controlled terms, historical names, phenotypes, subtypes, and relevant anatomy.
- Keep intervention, outcome, mechanism, and study-design blocks independently switchable.
- Preserve the original user wording as one query branch.

## Retrieval waves

1. **Sentinel**: recover known anchor studies and validate terminology.
2. **Discovery**: maximize recall across planned source classes.
3. **Confirmation**: focus on direct evidence for the decision claim.
4. **Expansion**: follow backward citations, forward citations, linked trials, authors, targets, and compounds.
5. **Challenge**: search for negative results, failed replications, safety signals, corrections, and retractions.
6. **Update**: repeat date-limited queries through the delivery `as_of` date.

Store every wave as an independent search event. Merge records through identifiers while preserving all query-to-record links.

## Temporal controls

Record the database, exact query, execution timestamp, requested publication cutoff, result count, and provider version when available. Apply publication cutoffs after retrieval when provider syntax or indexing dates are ambiguous. Distinguish online-first, issue, registry-update, and correction dates.

## Stop rules

Use concrete conditions: planned sources completed; anchor records recovered; two consecutive expansion waves add no decision-relevant evidence; predefined record or time budget reached; or further retrieval cannot change the decision. Report budget exhaustion and unavailable sources as limitations.
