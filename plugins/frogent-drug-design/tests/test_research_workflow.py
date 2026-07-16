"""Behavior tests for the executable literature intelligence workflow."""

import sys
import unittest
from unittest.mock import patch
from datetime import date, datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from frogent_plugin.contracts import ArtifactRef, ExecutionContext  # noqa: E402
from frogent_plugin.evidence import LiteratureRecord, SearchPlan  # noqa: E402
from frogent_plugin.harness import HarnessPolicy  # noqa: E402
from frogent_plugin.literature import LiteratureBatch  # noqa: E402
from frogent_plugin.literature import LiteratureQuery  # noqa: E402
from frogent_plugin.biomedical_providers import (  # noqa: E402
    EuropePMCProvider, NCBIConfig, OpenAlexProvider, PubMedProvider, UnpaywallFallback,
)
from frogent_plugin.research_types import (  # noqa: E402
    FullTextDocument, KnowledgeCandidate, ReaderClaim, ReaderReport, ResearchQuery,
    ResearchRequest, ScreeningAssessment,
)
from frogent_plugin.research_workflow import ResearchController  # noqa: E402
from frogent_plugin.research_v4 import run_v4_research  # noqa: E402
from frogent_plugin.v4_adapter import V4ChatRequest  # noqa: E402


def record(record_id: str, source: str, title: str, identifiers: dict[str, str], abstract: str = ""):
    return LiteratureRecord(record_id, "plan-1", source, title, datetime.now(timezone.utc), identifiers,
                            ArtifactRef("raw-" + record_id, title, "application/json", "memory://" + record_id),
                            date(2020, 1, 1), abstract)


class FakeProvider:
    def __init__(self, batches, metadata=None): self.batches, self.calls, self.details = batches, [], metadata or {}
    def search(self, query, context):
        self.calls.append((query.source, query.query))
        value = self.batches.get(query.query, ())
        if isinstance(value, Exception): raise value
        return LiteratureBatch(query, tuple(value), "fake-1")
    def metadata(self, record_id): return self.details.get(record_id, {})


class FakeOA:
    def __init__(self, values): self.values = values
    def resolve(self, item, context):
        value = self.values.get(item.id)
        if isinstance(value, Exception): raise value
        return value


class FakeReader:
    def __init__(self, malformed=()): self.malformed, self.tasks = set(malformed), []
    def read(self, task):
        self.tasks.append(task)
        if task.record.id in self.malformed: return {"bad": "shape"}
        direction = "counter" if "negative" in task.record.title.lower() else "support"
        claim = ReaderClaim("Mechanistic finding", "abstract:1", "neuronal model", "LRRK2",
                            "control", "pathology", direction, "reported", ("model-limited",))
        return ReaderReport(task.task_id, task.family_id, task.record.id, (claim,), direction == "counter",
                            "clear", ("needs replication",), ("human generality unresolved",))


class WrongIdentityReader(FakeReader):
    def read(self, task):
        report = super().read(task)
        return ReaderReport("wrong-task", report.family_id, report.record_id, report.claims,
                            report.counterevidence, report.integrity_status, report.limitations,
                            report.unresolved_questions)


class RejectingScreener:
    def assess(self, report, item):
        outcome = "exclude" if item.id == "A" else "uncertain"
        return ScreeningAssessment(outcome, ("test quality gate",))


class FakeSynthesizer:
    def synthesize(self, question, evidence, reports, gaps):
        ids = ",".join(item.id for item in evidence)
        return f"{question} | admitted={ids} | gaps={';'.join(gaps)}"


class FakeTransport:
    def __init__(self, responses): self.responses, self.calls = list(responses), []
    def get(self, url, params, headers={}):
        self.calls.append((url, dict(params)))
        return self.responses.pop(0)


class ResearchWorkflowBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.context = ExecutionContext("u", "c", "job", ROOT.resolve())
        self.plan = SearchPlan("plan-1", "LRRK2 and Parkinson disease", date(2024, 12, 31),
                               ("anchor", "challenge"), ("europe_pmc", "pubmed"), ("relevant",),
                               ("unrelated",), ("anchor and challenge complete",))
        self.anchor = record("A", "europe_pmc", "LRRK2 Rab substrate", {"doi": "10.1/anchor", "pmid": "1"})
        self.duplicate = record("A2", "pubmed", "LRRK2 Rab substrate", {"doi": "10.1/anchor", "pmid": "1"})
        self.counter = record("C", "europe_pmc", "Negative alpha synuclein result",
                              {"doi": "10.1/counter", "pmid": "2"})

    def request(self, candidates=()):
        calls = (ResearchQuery("europe-pmc.search", "europe_pmc", "anchor"),
                 ResearchQuery("pubmed.search", "pubmed", "anchor"),
                 ResearchQuery("europe-pmc.search", "europe_pmc", "challenge"))
        return ResearchRequest(self.plan, calls, tuple(candidates))

    def controller(self, europe=None, pubmed=None, oa=None, reader=None, screener=None):
        providers = {"europe-pmc.search": europe or FakeProvider({}),
                     "pubmed.search": pubmed or FakeProvider({})}
        return ResearchController(providers, {"europe_pmc": oa or FakeOA({})}, reader or FakeReader(),
                                  FakeSynthesizer(), HarnessPolicy(max_tool_calls=12), max_readers=2,
                                  screener=screener)

    def test_lrrk2_anchor_counterevidence_family_dedup_and_memory_gate(self):
        europe = FakeProvider({"anchor": (self.anchor,), "challenge": (self.counter,)})
        pubmed = FakeProvider({"anchor": (self.duplicate,)})
        result = self.controller(europe, pubmed).run(self.request(), self.context)
        self.assertEqual(2, len(result.reader_reports))
        self.assertEqual(2, len(result.raw_records))
        self.assertEqual(2, len(result.working_memory_ids))
        self.assertTrue(all(result.ledger.has_admitted(item) for item in result.working_memory_ids))
        self.assertIn("counter", {claim.direction for report in result.reader_reports for claim in report.claims})
        self.assertIn("admitted=", result.answer)

    def test_false_identifier_and_wrong_lab_knowledge_are_rejected_while_retrieval_continues(self):
        candidates = (KnowledgeCandidate("k1", "paper", "Imaginary paper", pmid="99999999",
                                         claim="LRRK2 claim", verification_query="99999999"),
                      KnowledgeCandidate("k2", "author_lab", "Wrong Lab", claim="Lab ownership",
                                         verification_query="Wrong Lab LRRK2"))
        europe = FakeProvider({"anchor": (self.anchor,), "challenge": (self.counter,)})
        result = self.controller(europe).run(self.request(candidates), self.context)
        self.assertEqual(("rejected", "rejected"), tuple(item.status for item in result.knowledge_candidates))
        self.assertGreater(len(result.working_memory_ids), 0)
        self.assertTrue(all("99999999" not in item.claim for item in result.ledger.admitted()))

    def test_oa_timeout_abstract_fallback_and_malformed_reader_are_isolated(self):
        body = "FULL TEXT SECRET " * 100
        oa = FakeOA({"A": TimeoutError("OA timeout"), "C": FullTextDocument(
            "C", ArtifactRef("oa-C", "counter.xml", "application/xml", "memory://oa/C"), body)})
        europe = FakeProvider({"anchor": (self.anchor,), "challenge": (self.counter,)})
        result = self.controller(europe, oa=oa, reader=FakeReader({"C"})).run(self.request(), self.context)
        self.assertEqual(1, len(result.reader_reports))
        self.assertTrue(any("OA timeout" in gap for gap in result.coverage_gaps))
        self.assertTrue(any("malformed reader" in gap for gap in result.coverage_gaps))
        self.assertNotIn(body, repr(result))
        self.assertGreater(len(result.working_memory_ids), 0)

    def test_checkpoint_resume_skips_queries_and_correction_revokes_memory(self):
        europe = FakeProvider({"anchor": (self.anchor,), "challenge": (self.counter,)})
        controller = self.controller(europe)
        interrupted = controller.run(self.request(), self.context, stop_after_retrieval=True)
        call_count = len(europe.calls)
        resumed = controller.run(self.request(), self.context, checkpoint=interrupted.checkpoint)
        self.assertEqual(call_count, len(europe.calls))
        self.assertGreater(len(resumed.working_memory_ids), 0)
        corrected = controller.run(self.request(), self.context, checkpoint=resumed.checkpoint,
                                   revoked_record_ids=("A",))
        self.assertEqual(call_count, len(europe.calls))
        self.assertTrue(all(item.record_id != "A" for item in corrected.ledger.admitted()))
        self.assertTrue(all("ev-A" != item for item in corrected.working_memory_ids))
        self.assertNotEqual(resumed.answer, corrected.answer)
        persisted = controller.run(self.request(), self.context, checkpoint=corrected.checkpoint)
        self.assertTrue(all(item.record_id != "A" for item in persisted.ledger.admitted()))

    def test_injectable_europe_pmc_pubmed_and_optional_provider_boundaries(self):
        epmc_json = (b'{"resultList":{"result":[{"pmid":"1","pmcid":"PMC1",'
                     b'"doi":"10.1/a","title":"LRRK2 anchor","firstPublicationDate":"2020-01-01",'
                     b'"abstractText":"abstract"}]}}')
        epmc = EuropePMCProvider(FakeTransport([epmc_json, b"<article><p>claim text</p></article>"]))
        query = LiteratureQuery("plan-1", "europe_pmc", "LRRK2", date(2024, 12, 31), 2)
        batch = epmc.search(query, self.context)
        self.assertEqual(("1",), tuple(item.id for item in batch.records))
        self.assertEqual("PMC1", batch.records[0].identifiers["pmcid"])
        self.assertIn("claim text", epmc.resolve(batch.records[0], self.context).text)
        related = EuropePMCProvider(FakeTransport([
            b'{"citationList":{"citation":[{"id":"c1"}]}}',
            b'{"referenceList":{"reference":[{"id":"r1"}]}}']))
        self.assertEqual(("c1",), related.related("MED", "1", "citations"))
        self.assertEqual(("r1",), related.related("MED", "1", "references"))
        esearch = b'{"esearchresult":{"idlist":["1"]}}'
        efetch = (b"<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>1</PMID><Article>"
                  b"<ArticleTitle>LRRK2 anchor</ArticleTitle><Abstract><AbstractText>abstract</AbstractText></Abstract>"
                  b"<Journal><JournalIssue><PubDate><Year>2020</Year></PubDate></JournalIssue></Journal>"
                  b"</Article></MedlineCitation><PubmedData><ArticleIdList><ArticleId IdType='doi'>10.1/a"
                  b"</ArticleId></ArticleIdList></PubmedData></PubmedArticle></PubmedArticleSet>")
        transport, sleeps = FakeTransport([esearch, efetch]), []
        pubmed = PubMedProvider(NCBIConfig("dev@example.org", "frogent"), transport,
                                clock=lambda: 0.0, sleeper=sleeps.append)
        pubmed_query = LiteratureQuery("plan-1", "pubmed", "LRRK2", date(2024, 12, 31), 2)
        self.assertEqual("1", pubmed.search(pubmed_query, self.context).records[0].id)
        self.assertEqual("dev@example.org", transport.calls[0][1]["email"])
        self.assertTrue(sleeps and sleeps[0] >= 1 / 3)
        with patch.dict("os.environ", {}, clear=True):
            self.assertIn("OPENALEX_API_KEY", OpenAlexProvider.from_env()[1])
            self.assertIn("UNPAYWALL_EMAIL", UnpaywallFallback.from_env()[1])

    def test_v4_adapter_emits_typed_answer_and_done_events(self):
        europe = FakeProvider({"anchor": (self.anchor,), "challenge": (self.counter,)})
        request = V4ChatRequest("u", "c", "job", self.plan.question)
        events = run_v4_research(request, self.context, self.request(), self.controller(europe))
        self.assertEqual("message.delta", events[-2].kind)
        self.assertEqual("done", events[-1].kind)
        self.assertGreater(events[-1].payload["admitted"], 0)

    def test_one_source_failure_does_not_block_later_counterevidence_query(self):
        europe = FakeProvider({"anchor": (self.anchor,), "challenge": (self.counter,)})
        pubmed = FakeProvider({"anchor": TimeoutError("PubMed unavailable")})
        result = self.controller(europe, pubmed).run(self.request(), self.context)
        self.assertEqual({"A", "C"}, {item.id for item in result.raw_records})
        self.assertTrue(any("PubMed unavailable" in gap for gap in result.coverage_gaps))

    def test_reader_identity_and_screening_assessment_control_memory(self):
        europe = FakeProvider({"anchor": (self.anchor,), "challenge": (self.counter,)})
        wrong = self.controller(europe, reader=WrongIdentityReader()).run(self.request(), self.context)
        self.assertFalse(wrong.reader_reports)
        self.assertTrue(any("identity mismatch" in gap for gap in wrong.coverage_gaps))
        gated = self.controller(europe, screener=RejectingScreener()).run(self.request(), self.context)
        self.assertFalse(gated.working_memory_ids)
        self.assertNotIn("ev-A", gated.answer)
        self.assertNotIn("ev-C", gated.answer)

    def test_verified_provider_metadata_exposes_author_leads_without_quality_promotion(self):
        metadata = {"A": {"authors": [{"fullName": "Ada Lab", "orcid": "0000-0001",
                                         "authorAffiliationDetailsList": {"authorAffiliation": [
                                             {"affiliation": "Institute"}]}},
                                        {"collectiveName": "LRRK2 Consortium",
                                         "affiliations": ["Network"]}]}}
        europe = FakeProvider({"anchor": (self.anchor,), "challenge": (self.counter,)}, metadata)
        result = self.controller(europe).run(self.request(), self.context)
        self.assertEqual("Ada Lab", result.author_leads[0].name)
        self.assertEqual(("Institute",), result.author_leads[0].affiliations)
        self.assertEqual("LRRK2 Consortium", result.author_leads[1].name)
        self.assertTrue(all(item.strength.value == "low" for item in result.ledger.admitted()))


if __name__ == "__main__":
    unittest.main()
