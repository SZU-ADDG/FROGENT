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
from frogent_plugin.evidence import SearchPlan  # noqa: E402
from frogent_plugin.harness import HarnessPolicy  # noqa: E402
from frogent_plugin.literature import LiteratureQuery  # noqa: E402
from frogent_plugin.research_types import (  # noqa: E402
    ReaderClaim, ReaderReport, ResearchQuery, ResearchRequest,
)
from frogent_plugin.research_workflow import ResearchController  # noqa: E402


class SmokeReader:
    def read(self, task):
        claim = ReaderClaim("Record addresses LRRK2 and Parkinson disease", "title/abstract",
                            "reported study model", "LRRK2", "not reported",
                            "Parkinson disease evidence", "reported", "not quantified")
        return ReaderReport(task.task_id, task.family_id, task.record.id, (claim,), False,
                            "clear", ("smoke reader does not assess effect size",), ())


class SmokeSynthesizer:
    def synthesize(self, question, evidence, reports, gaps):
        return f"{len(evidence)} admitted evidence excerpts; {len(gaps)} coverage gaps"


def main() -> int:
    context = ExecutionContext("smoke", "smoke", "literature-live-smoke", ROOT)
    epmc = EuropePMCProvider()
    plan = SearchPlan("live-smoke", "LRRK2 and Parkinson disease", date.today(),
                      ("LRRK2 AND Parkinson AND OPEN_ACCESS:Y",), ("europe_pmc",),
                      ("LRRK2/Parkinson evidence",), ("unrelated disease",), ("two records",))
    request = ResearchRequest(plan, (ResearchQuery("europe-pmc.search", "europe_pmc",
                              plan.queries[0], 2, "discovery"),))
    controller = ResearchController({"europe-pmc.search": epmc}, {"europe_pmc": epmc},
                                    SmokeReader(), SmokeSynthesizer(),
                                    HarnessPolicy(max_tool_calls=3), max_readers=2)
    result = controller.run(request, context)
    rows = []
    for record in result.raw_records:
        row = {"pmid": record.identifiers.get("pmid"), "doi": record.identifiers.get("doi"),
               "pmcid": record.identifiers.get("pmcid"),
               "oa_full_text_available": not any(
                   gap.startswith(record.id + ": abstract-only") for gap in result.coverage_gaps)}
        rows.append(row)
    output = {"europe_pmc": {"status": "completed", "records": rows,
              "admitted_count": len(result.working_memory_ids),
              "provider_calls": result.telemetry.provider_calls,
              "reader_tasks": result.telemetry.reader_tasks,
              "ordered_hit_ids": [item.record_id for item in result.hits],
              "coverage_gaps": list(result.coverage_gaps)}}
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
