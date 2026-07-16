#!/usr/bin/env python3
"""Small opt-in live smoke for biomedical literature adapters."""

import json
import os
import sys
from datetime import date
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from frogent_plugin.biomedical_providers import (  # noqa: E402
    EuropePMCProvider, NCBIConfig, OpenAlexProvider, PubMedProvider,
)
from frogent_plugin.contracts import ExecutionContext  # noqa: E402
from frogent_plugin.literature import LiteratureQuery  # noqa: E402


def main() -> int:
    context = ExecutionContext("smoke", "smoke", "literature-live-smoke", ROOT)
    epmc = EuropePMCProvider()
    query = LiteratureQuery("live-smoke", "europe_pmc",
                            "LRRK2 AND Parkinson AND OPEN_ACCESS:Y", date.today(), 3)
    batch = epmc.search(query, context)
    rows = []
    full_text_checked = False
    for record in batch.records:
        row = {"pmid": record.identifiers.get("pmid"), "doi": record.identifiers.get("doi"),
               "pmcid": record.identifiers.get("pmcid"), "oa_full_text_available": False}
        if not full_text_checked and record.identifiers.get("pmcid"):
            try:
                row["oa_full_text_available"] = epmc.resolve(record, context) is not None
            except Exception:
                row["oa_full_text_available"] = False
            full_text_checked = True
        rows.append(row)
    output = {"europe_pmc": {"status": "completed", "records": rows}}
    email = os.getenv("FROGENT_PUBMED_EMAIL", "")
    if email:
        provider = PubMedProvider(NCBIConfig(email, "frogent", os.getenv("NCBI_API_KEY", "")))
        pubmed_query = LiteratureQuery("live-smoke", "pubmed", "LRRK2 Parkinson", date.today(), 2)
        result = provider.search(pubmed_query, context)
        output["pubmed"] = {"status": "completed", "record_count": len(result.records)}
    else:
        output["pubmed"] = {"status": "skipped", "gap": "FROGENT_PUBMED_EMAIL is unset"}
    openalex, gap = OpenAlexProvider.from_env()
    if openalex and rows and rows[0].get("doi"):
        network = openalex.expand_work(str(rows[0]["doi"]))
        output["openalex"] = {"status": "completed", "author_count": len(network["authors"])}
    else:
        output["openalex"] = {"status": "skipped", "gap": gap or "no DOI returned"}
    print(json.dumps(output, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
