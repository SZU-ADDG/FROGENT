# Literature Provider Routing

Use Europe PMC for broad biomedical metadata, PMCID discovery, OA `fullTextXML`, and citation or reference expansion. Use PubMed ESearch plus batched EFetch for independent identifier and metadata verification. Always send configured `tool` and `email`; follow the NCBI three-request-per-second limit without an API key and ten-request-per-second limit with a key.

Use OpenAlex only when `OPENALEX_API_KEY` is configured. Its author, ORCID, institution, coauthor, and cited-by graph can prioritize expansion and maintain a watchlist; it cannot raise evidence quality. Record a coverage gap when the key is unavailable.

Use Unpaywall only as an OA link fallback when a contact email is configured. Preserve the publisher or repository URL as an artifact and keep license or accessibility uncertainty visible. A missing email is a coverage gap.

Treat model knowledge as search seeds. Verify PMIDs, DOIs, NCT identifiers, titles, and author or lab attribution against external metadata before screening. Failed verification remains outside evidence and working memory.

Send full text only to bounded reader workers. Main receives structured claim excerpts, locators, study context, effect direction and magnitude, limitations, integrity status, and unresolved questions. Full documents remain artifact-backed outside working memory.
