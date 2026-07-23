# Literature Intelligence

## Purpose

The literature workflow turns a biomedical question into traceable, screened evidence while
keeping model knowledge useful for search. Model memory proposes candidates; verified identifiers
and external records establish evidence.

## Retrieval

The default route uses Europe PMC for search, metadata, citations, references and OA JATS XML.
Configured providers add:

- PubMed ESearch and EFetch;
- OpenAlex author, institution, citation and repository discovery;
- Unpaywall OA fallback;
- NCBI BioC author manuscripts;
- ClinicalTrials.gov publication-to-registry evidence;
- repository PDFs with bounded extraction.

Queries include discovery, mechanism, challenge and counterevidence waves. Author affiliations,
ORCID, cited-by relationships and research-group leads can expand a bounded search. Canonical
study-family deduplication preserves every query-hit occurrence.

## Reading and screening

Full text is prepared in this order:

1. Europe PMC JATS;
2. NCBI BioC author manuscript;
3. verified OpenAlex repository PDF;
4. optional OA fallback;
5. abstract.

JATS, BioC, PDF page and registry markers provide stable Reader locators. A bounded worker pool
executes preparation and reading concurrently while returning reports in first-hit order. Per-paper
failures create coverage gaps and allow the rest of the batch to continue.

Reader reports must match task, family and record identity. Screening produces include, exclude or
uncertain decisions with reasons and evidence strength. Clear/corrected complete evidence can enter
at LOW strength; retracted records are excluded; abstract-only records retain a gap.

## Evidence and memory

Only admitted `EvidenceExcerpt` objects enter working memory. Every excerpt includes record,
claim, locator, strength and correction status. Synthesis citations and counterevidence must use
exact admitted evidence IDs. One evidence-binding repair is allowed; repeated failure returns a
bounded partial answer from admitted evidence.

SQLite stores checkpoints, telemetry, admitted evidence, answer versions and revocations. OA text
and raw provider bodies are not persisted. A resumed run preserves ordered hits, provider calls,
Reader telemetry and elapsed measurements.

## Agent behavior

The Agent leads with the best-supported answer and its practical implication. It actively searches
for disagreement, endpoint drift, registration gaps and study-family duplicates. Scientific
judgment remains available when literature is incomplete, with knowledge-led recommendations
clearly separated from verified evidence.

## Application path

`scripts/run_app.py` builds the maintained `app/` surface with `WebResearchManager`
and the FROGENT service. Login, history, attachment and SSE contracts remain.
Planner, Reader, Screener and Synthesizer can use direct subagents for batch work or the configured
typed model adapter for deployed app requests.

## Quality boundaries

- Provider results require identifier and schema validation.
- Registry protocol fields are planned evidence and cannot become observed outcomes.
- Repository metadata does not establish publisher-version equivalence.
- Reader/document caps emit explicit omissions.
- Claim strength never exceeds the admitted source and locator.

Harness and memory details are documented in [HARNESS.md](HARNESS.md). Active metrics and cases are
documented in [EVALUATION.md](EVALUATION.md).
