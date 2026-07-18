"""Behavior tests for the executable literature intelligence workflow."""

import sys
import threading
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
    UrllibTransport,
)
from frogent_plugin.research_types import (  # noqa: E402
    FullTextDocument, KnowledgeCandidate, ReaderClaim, ReaderReport, ResearchQuery,
    ResearchRequest, ScreeningAssessment,
)
from frogent_plugin.research_workflow import ResearchController  # noqa: E402
from frogent_plugin.research_reading import read_records  # noqa: E402
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
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


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
        full_xml = (b"<article><front><article-meta><title-group><article-title>Structured paper"
                    b"</article-title></title-group><abstract><p>Abstract claim</p></abstract>"
                    b"</article-meta></front><body><sec><title>Methods</title><p>method detail</p>"
                    b"</sec><sec><title>Results</title><p>claim text</p></sec><sec>"
                    b"<title>Discussion</title><p>limiting evidence</p></sec></body><back>"
                    b"<ref-list><ref><mixed-citation>reference secret</mixed-citation></ref>"
                    b"</ref-list></back></article>")
        epmc_transport = FakeTransport([epmc_json, full_xml])
        epmc = EuropePMCProvider(epmc_transport)
        query = LiteratureQuery("plan-1", "europe_pmc", "LRRK2", date(2024, 12, 31), 2)
        batch = epmc.search(query, self.context)
        self.assertEqual(("1",), tuple(item.id for item in batch.records))
        self.assertEqual("PMC1", batch.records[0].identifiers["pmcid"])
        full_text = epmc.resolve(batch.records[0], self.context).text
        self.assertIn("[TITLE] Structured paper", full_text)
        self.assertIn("[ABSTRACT 1 P1] Abstract claim", full_text)
        self.assertIn("[SECTION 2 Results P1] claim text", full_text)
        self.assertIn("[SECTION 3 Discussion P1] limiting evidence", full_text)
        self.assertNotIn("reference secret", full_text)
        self.assertEqual("", epmc.coverage_gap("1"))
        self.assertEqual(2, len(epmc_transport.calls))
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

    def test_europe_pmc_primary_failure_uses_section_preserving_bioc_author_manuscript(self):
        bioc = b"""<collection><infon key="license">custom-author-manuscript</infon><document>
        <passage><infon key="section_type">TITLE</infon><text>Structured manuscript</text></passage>
        <passage><infon key="section_type">ABSTRACT</infon><text>Abstract evidence</text></passage>
        <passage><infon key="section_type">METHODS</infon><text>Long methods</text></passage>
        <passage><infon key="section_type">RESULTS</infon><text>Late result evidence</text></passage>
        <passage><infon key="section_type">DISCUSS</infon><text>Limiting interpretation</text></passage>
        <passage><infon key="section_type">CONCLUSION</infon><text>Bounded conclusion</text></passage>
        <passage><infon key="section_type">CORRECTION</infon><text>Corrected value</text></passage>
        <passage><infon key="section_type">LIMITATION</infon><text>Small cohort</text></passage>
        <passage><infon key="section_type">TABLE</infon><text>Table 1 effect estimate</text></passage>
        <passage><infon key="section_type">FIG</infon><text>Figure 2 trend</text></passage>
        <passage><infon key="section_type">REF</infon><text>reference secret</text></passage>
        </document></collection>"""
        transport = FakeTransport([OSError("HTTP 404"), bioc])
        provider = EuropePMCProvider(transport)
        manuscript = record("M", "europe_pmc", "Manuscript", {"pmcid": "PMC5831666"})
        document = provider.resolve(manuscript, self.context)
        self.assertIn("[TITLE] Structured manuscript", document.text)
        for evidence in ("Late result evidence", "Limiting interpretation", "Bounded conclusion",
                         "Corrected value", "Small cohort", "Table 1 effect estimate", "Figure 2 trend"):
            self.assertIn(evidence, document.text)
        self.assertNotIn("reference secret", document.text)
        self.assertEqual("bioc-author-manuscript-M", document.artifact.id)
        self.assertIn("author_manuscript", document.artifact.name)
        self.assertIn("license=custom-author-manuscript", document.artifact.name)
        self.assertEqual(EuropePMCProvider.BIOC_BASE + "/PMC5831666/unicode", document.artifact.uri)
        gap = provider.coverage_gap("M")
        self.assertIn("Europe PMC fullTextXML failed: OSError: HTTP 404", gap)
        self.assertIn("NCBI BioC author_manuscript fallback used", gap)
        self.assertIn("open-access and publisher-version status not asserted", gap)
        self.assertEqual(2, len(transport.calls))

    def test_europe_pmc_and_bioc_failure_preserve_both_gaps_and_abstract_fallback(self):
        provider = EuropePMCProvider(FakeTransport([
            OSError("primary unavailable"), OSError("BioC unavailable")]))
        manuscript = record("M", "europe_pmc", "Manuscript", {"pmcid": "PMC1"})
        self.assertIsNone(provider.resolve(manuscript, self.context))
        gap = provider.coverage_gap("M")
        self.assertIn("Europe PMC fullTextXML failed: OSError: primary unavailable", gap)
        self.assertIn("NCBI BioC author_manuscript fallback failed: OSError: BioC unavailable", gap)
        resolver = EuropePMCProvider(FakeTransport([
            OSError("primary unavailable"), OSError("BioC unavailable")]))
        reader = FakeReader()
        reports, gaps, _ = read_records((manuscript,), {"europe_pmc": resolver}, reader,
                                        self.context, max_workers=1)
        self.assertEqual(1, len(reports))
        self.assertEqual("Manuscript", reader.tasks[0].text)
        self.assertIsNone(reader.tasks[0].full_text_artifact)
        self.assertTrue(any("primary unavailable" in item and "BioC unavailable" in item
                            for item in gaps))
        self.assertIn("M: abstract-only evidence", gaps)

    def test_urllib_transport_has_no_default_timeout_and_accepts_positive_override(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return b"ok"

        with patch("frogent_plugin.biomedical_providers.urllib.request.urlopen",
                   side_effect=(Response(), Response())) as urlopen:
            self.assertEqual(b"ok", UrllibTransport().get("https://example.test", {}))
            self.assertEqual(b"ok", UrllibTransport(12.5).get("https://example.test", {}))
        self.assertEqual({}, urlopen.call_args_list[0].kwargs)
        self.assertEqual({"timeout": 12.5}, urlopen.call_args_list[1].kwargs)
        for invalid in (0, -1, float("nan"), float("inf")):
            with self.subTest(timeout=invalid), self.assertRaisesRegex(ValueError, "positive finite"):
                UrllibTransport(invalid)

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

    def test_oa_reader_pipelines_overlap_preserve_order_and_isolate_oa_failure(self):
        first = record("Z", "europe_pmc", "First paper", {"doi": "10.1/z"}, "first abstract")
        second = record("A", "europe_pmc", "Second paper", {"doi": "10.1/a"}, "second abstract")
        plan = SearchPlan("plan-1", "Q", date(2024, 12, 31), ("Q",), ("europe_pmc",),
                          ("relevant",), ("unrelated",), ("complete",))
        request = ResearchRequest(plan, (ResearchQuery(
            "europe-pmc.search", "europe_pmc", "Q", 2),))

        class Provider:
            def search(self, query, context):
                return LiteratureBatch(query, (first, second), "fake")

        resolve_barrier, read_barrier = threading.Barrier(2), threading.Barrier(2)
        second_read = threading.Event()

        class Resolver:
            def resolve(self, item, context):
                resolve_barrier.wait(timeout=2)
                return FullTextDocument(item.id, ArtifactRef(
                    "oa-" + item.id, item.id + ".xml", "application/xml", "memory://" + item.id),
                    "[TITLE] " + item.title + "\n[SECTION 1 Results P1] full " + item.id)

        class OrderedReader:
            def read(self, task):
                read_barrier.wait(timeout=2)
                if task.record.id == "Z":
                    if not second_read.wait(timeout=2):
                        raise AssertionError("second reader pipeline did not overlap")
                else:
                    second_read.set()
                claim = ReaderClaim("claim", "Results P1", "model", "intervention",
                                    "control", "outcome", "support", "reported")
                return ReaderReport(task.task_id, task.family_id, task.record.id, (claim,), False,
                                    "clear", (), ())

        controller = ResearchController({"europe-pmc.search": Provider()},
            {"europe_pmc": Resolver()}, OrderedReader(), FakeSynthesizer(),
            HarnessPolicy(max_tool_calls=2), max_readers=2)
        result = controller.run(request, self.context)
        self.assertEqual(("Z", "A"), tuple(item.record_id for item in result.reader_reports))
        completed = tuple(event.payload["record_id"] for event in result.events
                          if event.kind == "tool.completed" and event.payload.get("name") == "reader")
        self.assertEqual(("Z", "A"), completed)

        class PartialResolver:
            def resolve(self, item, context):
                if item.id == "Z":
                    raise OSError("OA unavailable")
                return FullTextDocument(item.id, ArtifactRef(
                    "oa-A", "A.xml", "application/xml", "memory://A"), "full second evidence")

        class CapturingReader:
            def __init__(self): self.tasks = {}
            def read(self, task):
                self.tasks[task.record.id] = task
                claim = ReaderClaim("claim", "source P1", "model", "intervention",
                                    "control", "outcome", "support", "reported")
                return ReaderReport(task.task_id, task.family_id, task.record.id, (claim,), False,
                                    "clear", (), ())

        reader = CapturingReader()
        partial = ResearchController({"europe-pmc.search": Provider()},
            {"europe_pmc": PartialResolver()}, reader, FakeSynthesizer(),
            HarnessPolicy(max_tool_calls=2), max_readers=2).run(request, self.context)
        self.assertEqual(("Z", "A"), tuple(item.record_id for item in partial.reader_reports))
        self.assertEqual(("first abstract", None),
                         (reader.tasks["Z"].text, reader.tasks["Z"].full_text_artifact))
        self.assertEqual("full second evidence", reader.tasks["A"].text)
        self.assertIsNotNone(reader.tasks["A"].full_text_artifact)
        self.assertTrue(any("Z: OSError: OA unavailable" in gap for gap in partial.coverage_gaps))
        self.assertTrue(any("Z: abstract-only evidence" in gap for gap in partial.coverage_gaps))


if __name__ == "__main__":
    unittest.main()
