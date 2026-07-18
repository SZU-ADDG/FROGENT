"""Behavior tests for the executable literature intelligence workflow."""

import sys
import threading
import unittest
import json
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
from frogent_plugin.clinical_trials import ClinicalTrialsResolver  # noqa: E402
from frogent_plugin.reader_text import pack_reader_text  # noqa: E402
from frogent_plugin.research_types import (  # noqa: E402
    FullTextDocument, KnowledgeCandidate, ReaderClaim, ReaderReport, ResearchQuery,
    ResearchRequest, ScreeningAssessment,
)
from frogent_plugin.research_workflow import ResearchController  # noqa: E402
from frogent_plugin.research_reading import read_records  # noqa: E402
from frogent_plugin.research_factory import OAFallbackResolver  # noqa: E402
from frogent_plugin.repository_fulltext import (  # noqa: E402
    OpenAlexRepositoryLocator, OpenAlexRepositoryResolver,
)
from frogent_plugin.pdf_text import PypdfTextExtractor  # noqa: E402
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


def trial_payload(nct_id="NCT04154072", pmid="38101901", reference_type="DERIVED"):
    return {"hasResults": False, "protocolSection": {
        "identificationModule": {"nctId": nct_id, "briefTitle": "NLY01 in Early Parkinson Disease",
                                 "officialTitle": "A Study of NLY01 in Early Parkinson Disease"},
        "statusModule": {"overallStatus": "COMPLETED",
                         "startDateStruct": {"date": "2020-02-03"},
                         "completionDateStruct": {"date": "2023-01-17"},
                         "lastUpdatePostDateStruct": {"date": "2024-03-04", "type": "ACTUAL"}},
        "designModule": {"studyType": "INTERVENTIONAL", "phases": ["PHASE_2"],
                         "designInfo": {"allocation": "RANDOMIZED",
                                        "maskingInfo": {"masking": "QUADRUPLE"}},
                         "enrollmentInfo": {"count": 255, "type": "ACTUAL"}},
        "armsInterventionsModule": {"armGroups": [
            {"label": "NLY01 low dose", "type": "EXPERIMENTAL",
             "interventionNames": ["DRUG: NLY01 low dose"]},
            {"label": "NLY01 high dose", "type": "EXPERIMENTAL",
             "interventionNames": ["DRUG: NLY01 high dose"]},
            {"label": "Placebo", "type": "PLACEBO_COMPARATOR",
             "interventionNames": ["DRUG: Placebo"]}]},
        "outcomesModule": {
            "primaryOutcomes": [{"measure": "MDS-UPDRS Parts II and III",
                                  "timeFrame": "Baseline to 36 weeks"}],
            "secondaryOutcomes": [{"measure": "Clinical Global Impression",
                                    "timeFrame": "36 weeks"}]},
        "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Study Sponsor",
                                                         "class": "INDUSTRY"}},
        "referencesModule": {"references": [{"pmid": pmid, "type": reference_type}]}}}


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
                  b"</Article><DataBankList><DataBank><DataBankName>ClinicalTrials.gov</DataBankName>"
                  b"<AccessionNumberList><AccessionNumber>NCT04154072</AccessionNumber>"
                  b"<AccessionNumber>not-a-trial</AccessionNumber><AccessionNumber>NCT04232969"
                  b"</AccessionNumber><AccessionNumber>NCT04154072</AccessionNumber>"
                  b"</AccessionNumberList></DataBank></DataBankList></MedlineCitation>"
                  b"<PubmedData><ArticleIdList><ArticleId IdType='doi'>10.1/a"
                  b"</ArticleId></ArticleIdList></PubmedData></PubmedArticle></PubmedArticleSet>")
        transport, sleeps = FakeTransport([esearch, efetch]), []
        pubmed = PubMedProvider(NCBIConfig("dev@example.org", "frogent"), transport,
                                clock=lambda: 0.0, sleeper=sleeps.append)
        pubmed_query = LiteratureQuery("plan-1", "pubmed", "LRRK2", date(2024, 12, 31), 2)
        pubmed_record = pubmed.search(pubmed_query, self.context).records[0]
        self.assertEqual("1", pubmed_record.id)
        self.assertEqual(("NCT04154072", "NCT04232969"),
                         (pubmed_record.identifiers["nct"], pubmed_record.identifiers["nct_2"]))
        self.assertNotIn("not-a-trial", pubmed_record.identifiers.values())
        self.assertEqual("dev@example.org", transport.calls[0][1]["email"])
        self.assertTrue(sleeps and sleeps[0] >= 1 / 3)
        with patch.dict("os.environ", {}, clear=True):
            self.assertIn("OPENALEX_API_KEY", OpenAlexProvider.from_env()[1])
            self.assertIn("UNPAYWALL_EMAIL", UnpaywallFallback.from_env()[1])

    def test_clinical_trials_direct_identity_and_compact_nly01_evidence(self):
        study = trial_payload()
        transport = FakeTransport([json.dumps(study).encode()])
        resolver = ClinicalTrialsResolver(transport)
        item = record("38101901", "pubmed", "NLY01 publication",
                      {"pmid": "38101901", "nct": "NCT04154072"})
        text = resolver.resolve(item, self.context)
        self.assertEqual((ClinicalTrialsResolver.BASE + "/studies/NCT04154072",
                          {"format": "json"}), transport.calls[0])
        for expected in ("[REGISTRY NCT04154072 STATUS] overallStatus=COMPLETED",
                         "lastUpdatePostDate=2024-03-04; lastUpdatePostType=ACTUAL",
                         "link_method=pubmed_accession",
                         "snapshot=current_mutable; historical_as_of_reconstruction=not_established",
                         "[REGISTRY NCT04154072 ENROLLMENT] count=255; type=ACTUAL",
                         "[REGISTRY NCT04154072 SPONSOR] lead=Study Sponsor; class=INDUSTRY",
                         "[REGISTRY NCT04154072 ARM 3] label=Placebo",
                         "[REGISTRY NCT04154072 PLANNED PRIMARY OUTCOME 1]",
                         "timeFrame=Baseline to 36 weeks",
                         "hasResults=false; resultsFirstPosted=not_reported; observedResults=none; "
                         "registry supplies no observed efficacy/safety result"):
            self.assertIn(expected, text)
        mismatch = trial_payload("NCT00000001")
        failed = ClinicalTrialsResolver(FakeTransport([json.dumps(mismatch).encode()]))
        self.assertEqual("", failed.resolve(item, self.context))
        self.assertIn("direct study identity mismatch", failed.coverage_gap(item.id))
        malformed = ClinicalTrialsResolver(FakeTransport([]))
        bad = record("bad", "pubmed", "Bad trial", {"nct": "NCT123"})
        self.assertEqual("", malformed.resolve(bad, self.context))
        self.assertIn("malformed NCT identifier", malformed.coverage_gap("bad"))
        bounded = ClinicalTrialsResolver(FakeTransport([]), max_studies=1)
        too_many = record("many", "pubmed", "Multiple trials",
                          {"nct": "NCT04154072", "nct_2": "NCT04232969"})
        self.assertEqual("", bounded.resolve(too_many, self.context))
        self.assertIn("direct NCT identifiers exceed", bounded.coverage_gap("many"))
        posted = {**study, "hasResults": True, "protocolSection": {**study["protocolSection"],
                  "statusModule": {**study["protocolSection"]["statusModule"],
                                   "resultsFirstPostDateStruct": {"date": "2024-05-01"}}}}
        posted_text = ClinicalTrialsResolver(FakeTransport([json.dumps(posted).encode()])).resolve(
            item, self.context)
        self.assertIn("resultsFirstPosted=2024-05-01; observedResults=posted; "
                      "resultsSection values not extracted", posted_text)
        ignored = record("ignored", "pubmed", "Unrelated accession",
                         {"other_registry": "NCT04154072"})
        unrelated = ClinicalTrialsResolver(FakeTransport([]))
        self.assertEqual("", unrelated.resolve(ignored, self.context))
        self.assertEqual("", unrelated.coverage_gap("ignored"))

    def test_registry_secondary_outcomes_are_bounded_with_omitted_count(self):
        study = trial_payload()
        secondary = [{"measure": f"Secondary measure {index}", "timeFrame": f"Week {index}",
                      "description": "secondary hidden description"}
                     for index in range(1, 46)]
        study["protocolSection"]["outcomesModule"]["secondaryOutcomes"] = secondary
        item = record("38101901", "pubmed", "NLY01 publication",
                      {"pmid": "38101901", "nct": "NCT04154072"})
        text = ClinicalTrialsResolver(FakeTransport([json.dumps(study).encode()])).resolve(
            item, self.context)
        self.assertEqual(10, text.count("PLANNED SECONDARY OUTCOME "))
        self.assertIn("[REGISTRY NCT04154072 SECONDARY OUTCOMES OMITTED] count=35", text)
        self.assertIn("[REGISTRY NCT04154072 PLANNED PRIMARY OUTCOME 1]", text)
        self.assertNotIn("secondary hidden description", text)

    def test_primary_outcome_keeps_bounded_off_medication_description(self):
        study = trial_payload("NCT01971242", "28781108")
        description = ("Change in Movement Disorder Society Unified Parkinson's Disease Rating "
                       "Scale MDS-UPDRS part 3 score in the practically defined OFF medication state. "
                       + "Detailed protocol qualifier. " * 80)
        study["protocolSection"]["outcomesModule"]["primaryOutcomes"] = [{
            "measure": "Efficacy", "timeFrame": "Baseline to week 36",
            "description": description}]
        item = record("28781108", "pubmed", "Trial publication",
                      {"pmid": "28781108", "nct": "NCT01971242"})
        text = ClinicalTrialsResolver(FakeTransport([json.dumps(study).encode()])).resolve(
            item, self.context)
        primary = next(line for line in text.splitlines() if "PLANNED PRIMARY OUTCOME 1" in line)
        self.assertIn("MDS-UPDRS part 3", primary)
        self.assertIn("OFF medication state", primary)
        self.assertIn("[TRUNCATED: primary outcome description limit]", primary)
        self.assertLess(len(primary), 1500)

    def test_pmid_discovery_accepts_only_result_or_derived_and_is_bounded_deduped(self):
        background_a = trial_payload("NCT04431713", "28781108", "BACKGROUND")
        background_b = trial_payload("NCT03840005", "28781108", "BACKGROUND")
        derived = trial_payload("NCT01971242", "28781108", "DERIVED")
        payload = {"studies": [background_a, background_b, derived, derived], "totalCount": 4}
        transport = FakeTransport([json.dumps(payload).encode()])
        resolver = ClinicalTrialsResolver(transport, max_studies=1)
        item = record("28781108", "europe_pmc", "Trial publication", {"pmid": "28781108"})
        text = resolver.resolve(item, self.context)
        self.assertEqual({"query.term": "AREA[ReferencePMID]28781108", "pageSize": "25",
                          "countTotal": "true", "format": "json"}, transport.calls[0][1])
        self.assertEqual(1, text.count("[REGISTRY SOURCE NCT01971242]"))
        self.assertIn("link_method=ctg_reference; inputPMID=28781108; reference_type=DERIVED", text)
        self.assertNotIn("NCT04431713", text)
        self.assertNotIn("NCT03840005", text)
        self.assertEqual("", resolver.coverage_gap(item.id))
        quiet = ClinicalTrialsResolver(FakeTransport([json.dumps(
            {"studies": [background_a, background_b]}).encode()]))
        self.assertEqual("", quiet.resolve(item, self.context))
        self.assertEqual("", quiet.coverage_gap(item.id))
        empty = ClinicalTrialsResolver(FakeTransport([b'{"totalCount":0}']))
        self.assertEqual("", empty.resolve(item, self.context))
        self.assertEqual("", empty.coverage_gap(item.id))
        conflict = {**derived, "protocolSection": {**derived["protocolSection"],
                    "identificationModule": {**derived["protocolSection"]["identificationModule"],
                                               "briefTitle": "Conflicting title"}}}
        conflicted = ClinicalTrialsResolver(FakeTransport([json.dumps(
            {"studies": [derived, conflict]}).encode()]))
        self.assertEqual("", conflicted.resolve(item, self.context))
        self.assertIn("conflicting duplicate trial identity", conflicted.coverage_gap(item.id))
        retracted = {**derived, "protocolSection": {**derived["protocolSection"],
                     "referencesModule": {**derived["protocolSection"]["referencesModule"],
                                          "retractions": [{"pmid": "28781108"}]}}}
        integrity = ClinicalTrialsResolver(FakeTransport([json.dumps(
            {"studies": [retracted]}).encode()]))
        self.assertEqual("", integrity.resolve(item, self.context))
        self.assertIn("appears in registry retractions", integrity.coverage_gap(item.id))

    def test_registry_evidence_is_prioritized_and_reader_failures_stay_local(self):
        registry_text = "\n".join(("[REGISTRY SOURCE NCT04154072] https://clinicaltrials.gov/study/NCT04154072",
            "[REGISTRY NCT04154072 ENROLLMENT] count=255; type=ACTUAL",
            "[REGISTRY NCT04154072 PLANNED PRIMARY OUTCOME 1] measure=Motor score; timeFrame=36 weeks",
            "[REGISTRY NCT04154072 RESULTS] hasResults=false; resultsFirstPosted=not_reported"))
        long_text = ("[TITLE] Long paper\n[SECTION 1 Methods P1] " + "method " * 2000
                     + "\n" + registry_text)
        packed = pack_reader_text(long_text, 520)
        self.assertLessEqual(len(packed), 520)
        self.assertIn("[REGISTRY NCT04154072 ENROLLMENT]", packed)
        self.assertIn("[REGISTRY NCT04154072 RESULTS]", packed)

        first = record("P1", "europe_pmc", "First publication", {"pmid": "1"}, "abstract one")
        second = record("P2", "europe_pmc", "Second publication", {"pmid": "2"}, "abstract two")
        plan = SearchPlan("plan-1", "Q", date(2024, 12, 31), ("Q",), ("europe_pmc",),
                          ("relevant",), ("unrelated",), ("complete",))
        request = ResearchRequest(plan, (ResearchQuery(
            "europe-pmc.search", "europe_pmc", "Q", 2),))

        class Provider:
            def search(self, query, context): return LiteratureBatch(query, (first, second), "fake")
        class Registry:
            def resolve(self, item, context):
                if item.id == "P1": raise OSError("registry unavailable")
                return registry_text
            def coverage_gap(self, record_id): return ""
        reader = FakeReader()
        result = ResearchController({"europe-pmc.search": Provider()}, {}, reader,
            FakeSynthesizer(), HarnessPolicy(max_tool_calls=2), max_readers=2,
            registry_resolver=Registry()).run(request, self.context)
        self.assertEqual(("P1", "P2"), tuple(report.record_id for report in result.reader_reports))
        self.assertEqual("abstract one", reader.tasks[0].text)
        self.assertIn("[REGISTRY SOURCE BOUNDARY]", reader.tasks[1].text)
        self.assertIn("hasResults=false", reader.tasks[1].text)
        self.assertTrue(any("P1: registry failed: OSError: registry unavailable" in gap
                            for gap in result.coverage_gaps))

    def test_pdf_article_survives_large_registry_suffix_under_reader_bound(self):
        pages = []
        for page in range(1, 12):
            lead = "UCL publication title " if page == 1 else ""
            effect = "primary effect estimate 0.92 " if page == 8 else ""
            pages.append(f"[PDF PAGE {page}] {lead}{effect}" + "publication evidence " * 255)
        article = "\n".join(pages)
        registry_lines = [
            "[REGISTRY SOURCE NCT04232969] link_method=ctg_reference; snapshot=current_mutable",
            "[REGISTRY NCT04232969 ENROLLMENT] count=194; type=ACTUAL",
            "[REGISTRY NCT04232969 PLANNED PRIMARY OUTCOME 1] measure=Efficacy; timeFrame=96 weeks; "
            "description=MDS-UPDRS part 3 in the practically defined OFF medication state",
            "[REGISTRY NCT04232969 RESULTS] hasResults=false; observedResults=none",
        ]
        registry_lines.extend(
            f"[REGISTRY NCT04232969 PLANNED SECONDARY OUTCOME {index}] "
            f"measure={'secondary protocol field ' * 5}{index}; timeFrame=96 weeks"
            for index in range(1, 46))
        registry_lines.append("[REGISTRY NCT04232969 SECONDARY OUTCOMES OMITTED] count=35")
        registry = "\n".join(registry_lines)
        combined = article + "\n[REGISTRY SOURCE BOUNDARY]\n" + registry
        self.assertTrue(58_000 < len(article) < 60_000)
        self.assertGreater(len(registry), 8_000)
        packed = pack_reader_text(combined, 60_000)
        self.assertLessEqual(len(packed), 60_000)
        self.assertIn("UCL publication title", packed)
        self.assertIn("primary effect estimate 0.92", packed)
        self.assertGreaterEqual(packed.count("[PDF PAGE "), 4)
        for expected in ("[REGISTRY SOURCE NCT04232969]", "count=194",
                         "PLANNED PRIMARY OUTCOME 1", "MDS-UPDRS part 3",
                         "OFF medication state", "hasResults=false",
                         "SECONDARY OUTCOMES OMITTED] count=35"):
            self.assertIn(expected, packed)

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

    def test_openalex_selects_only_repository_location_and_propagates_pdf_provenance(self):
        class HeaderTransport(FakeTransport):
            def __init__(self, responses):
                super().__init__(responses)
                self.headers = []
            def get(self, url, params, headers={}):
                self.headers.append(dict(headers))
                return super().get(url, params, headers)

        payload = {
            "ids": {"pmid": "https://pubmed.ncbi.nlm.nih.gov/39919773",
                    "doi": "https://doi.org/10.1016/S0140-6736(24)02808-3"},
            "best_oa_location": {"landing_page_url": "https://publisher.test/article",
                                 "pdf_url": "https://publisher.test/article.pdf"},
            "locations": [
                {"landing_page_url": "https://publisher.test/article",
                 "pdf_url": "https://publisher.test/article.pdf", "version": "publishedVersion",
                 "license": "cc-by", "source": {"type": "journal", "display_name": "Journal"}},
                {"landing_page_url": "https://discovery.ucl.ac.uk/id/eprint/10204617/",
                 "pdf_url": "https://discovery.ucl.ac.uk/10204617/1/paper.pdf",
                 "version": "submittedVersion", "license": "cc-by",
                 "source": {"type": "repository", "display_name": "UCL Discovery"}},
            ],
        }
        encoded = json.dumps(payload).encode()
        transport = HeaderTransport([encoded, encoded, b"%PDF-1.7 repository bytes"])
        locator = OpenAlexRepositoryLocator(transport)
        location = locator.locate(pmid="39919773", doi="10.1016/S0140-6736(24)02808-3")
        self.assertEqual("UCL Discovery", location.repository_name)
        self.assertEqual("discovery.ucl.ac.uk", location.repository_host)
        self.assertEqual("submittedVersion", location.version)
        self.assertEqual("cc-by", location.license)
        self.assertEqual({"select": "ids,locations"}, transport.calls[0][1])
        self.assertIn("/works/pmid:39919773", transport.calls[0][0])
        keyed = FakeTransport([encoded])
        OpenAlexRepositoryLocator(keyed, "configured-key").locate(pmid="39919773",
            doi="10.1016/S0140-6736(24)02808-3")
        self.assertEqual({"select": "ids,locations", "api_key": "configured-key"}, keyed.calls[0][1])

        class Extractor:
            def __init__(self): self.calls = []
            def extract(self, content, artifact):
                self.calls.append((content, artifact))
                return "[TITLE] Repository manuscript\n[SECTION 1 Results P1] result evidence"

        extractor = Extractor()
        resolver = OpenAlexRepositoryResolver(locator, extractor, transport)
        manuscript = record("R", "europe_pmc", "Repository paper", {
            "pmid": "39919773", "doi": "10.1016/S0140-6736(24)02808-3"})
        document = resolver.resolve(manuscript, self.context)
        self.assertIn("result evidence", document.text)
        self.assertEqual("application/pdf", document.artifact.media_type)
        self.assertEqual("https://discovery.ucl.ac.uk/10204617/1/paper.pdf", document.artifact.uri)
        for value in ("repository=UCL Discovery", "host=discovery.ucl.ac.uk",
                      "version=submittedVersion", "license=cc-by",
                      "landing=https://discovery.ucl.ac.uk/id/eprint/10204617/"):
            self.assertIn(value, document.artifact.name)
        self.assertEqual(b"%PDF-1.7 repository bytes", extractor.calls[0][0])
        self.assertEqual(({}, {}, {"User-Agent":
            "FROGENT/1.0 (biomedical literature research)"}), tuple(transport.headers))
        self.assertIn("repository PDF evidence extracted", resolver.coverage_gap("R"))

    def test_openalex_repository_identity_filter_and_extractor_unavailable_are_fail_closed(self):
        publisher_only = {"ids": {"pmid": "https://pubmed.ncbi.nlm.nih.gov/7"},
                          "best_oa_location": {"pdf_url": "https://repo.test/best.pdf"},
                          "locations": [
                              {"landing_page_url": "https://publisher.test/article",
                               "pdf_url": "https://publisher.test/article.pdf",
                               "source": {"type": "journal", "display_name": "Journal"}},
                              {"landing_page_url": "https://pubmed.ncbi.nlm.nih.gov/7",
                               "pdf_url": None,
                               "source": {"type": "repository", "display_name": "PubMed"}},
                          ]}
        locator = OpenAlexRepositoryLocator(FakeTransport([json.dumps(publisher_only).encode()]))
        self.assertIsNone(locator.locate(pmid="7"))
        with self.assertRaisesRegex(ValueError, "requires DOI or PMID"):
            locator.locate()
        mismatch = {**publisher_only, "ids": {"pmid": "https://pubmed.ncbi.nlm.nih.gov/8"}}
        with self.assertRaisesRegex(ValueError, "PMID identity mismatch"):
            OpenAlexRepositoryLocator(FakeTransport([
                json.dumps(mismatch).encode()])).locate(pmid="7")

        repository = {"ids": {"pmid": "https://pubmed.ncbi.nlm.nih.gov/7"},
                      "locations": [{"landing_page_url": "https://repo.test/item/7",
                                     "pdf_url": "https://repo.test/item/7.pdf",
                                     "version": "submittedVersion", "license": "cc-by",
                                     "source": {"type": "repository",
                                                "display_name": "Institution Repository"}}]}

        class Primary:
            def resolve(self, item, context): return None
            def coverage_gap(self, record_id): return "Europe PMC/BioC unavailable"

        transport = FakeTransport([json.dumps(repository).encode()])
        repository_resolver = OpenAlexRepositoryResolver(OpenAlexRepositoryLocator(transport))
        resolver = OAFallbackResolver(Primary(), repository=repository_resolver)
        item = record("7", "europe_pmc", "Repository candidate", {"pmid": "7"}, "abstract evidence")
        reader = FakeReader()
        reports, gaps, _ = read_records((item,), {"europe_pmc": resolver}, reader,
                                        self.context, max_workers=1)
        self.assertEqual(1, len(reports))
        self.assertEqual("abstract evidence", reader.tasks[0].text)
        self.assertIsNone(reader.tasks[0].full_text_artifact)
        combined = " ".join(gaps)
        self.assertIn("Europe PMC/BioC unavailable", combined)
        self.assertIn("repository=Institution Repository", combined)
        self.assertIn("version=submittedVersion", combined)
        self.assertIn("license=cc-by", combined)
        self.assertIn("repository PDF extraction unavailable", combined)
        self.assertEqual(1, len(transport.calls))

        class CountingExtractor:
            def __init__(self): self.calls = 0
            def extract(self, content, artifact):
                self.calls += 1
                return "must not be called"

        encoded = json.dumps(repository).encode()
        cases = ((b"<html>temporary error</html>", 100, "not PDF (%PDF- signature missing)"),
                 (b"%PDF-" + b"x" * 20, 8, "exceeds 8 byte limit"))
        for content, limit, expected in cases:
            with self.subTest(repository_response=expected):
                extractor = CountingExtractor()
                attempt = FakeTransport([encoded, content])
                boundary = OpenAlexRepositoryResolver(OpenAlexRepositoryLocator(attempt), extractor,
                                                       attempt, max_pdf_bytes=limit)
                self.assertIsNone(boundary.resolve(item, self.context))
                self.assertIn(expected, boundary.coverage_gap("7"))
                self.assertEqual(0, extractor.calls)
        for invalid in (0, -1, float("nan"), float("inf"), True):
            with self.subTest(pdf_limit=invalid), self.assertRaisesRegex(
                    ValueError, "positive and finite"):
                OpenAlexRepositoryResolver(OpenAlexRepositoryLocator(FakeTransport([])),
                                           max_pdf_bytes=invalid)

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

    def test_pypdf_extractor_preserves_pages_bounds_and_clean_failures(self):
        artifact = ArtifactRef("pdf", "paper.pdf", "application/pdf", "memory://paper.pdf")

        class Page:
            def __init__(self, text): self.text = text
            def extract_text(self): return self.text

        class Module:
            def __init__(self, pages=(), encrypted=False, error=None):
                self.pages, self.encrypted, self.error = pages, encrypted, error
            def PdfReader(self, stream):
                if self.error:
                    raise self.error
                return type("Reader", (), {"pages": self.pages,
                                            "is_encrypted": self.encrypted})()

        pages = (Page(" first\npage  text "), Page("second page"), Page("third page"))
        bounded = PypdfTextExtractor(2, 1000, module=Module(pages)).extract(b"%PDF-1.7", artifact)
        self.assertEqual("[PDF PAGE 1] first page text\n[PDF PAGE 2] second page\n"
                         "[PDF TEXT TRUNCATED: page limit]", bounded)
        self.assertNotIn("PAGE 3", bounded)
        truncated = PypdfTextExtractor(3, 75, module=Module(pages)).extract(b"%PDF-1.7", artifact)
        self.assertLessEqual(len(truncated), 75)
        self.assertTrue(truncated.startswith("[PDF PAGE 1] first"))
        self.assertTrue(truncated.endswith("[PDF TEXT TRUNCATED: character limit]"))
        with self.assertRaisesRegex(ValueError, "OCR required"):
            PypdfTextExtractor(module=Module((Page(""), Page(None)))).extract(b"%PDF-1.7", artifact)
        with self.assertRaisesRegex(ValueError, "encrypted PDF"):
            PypdfTextExtractor(module=Module(encrypted=True)).extract(b"%PDF-1.7", artifact)
        with self.assertRaisesRegex(ValueError, "PDF is unreadable.*malformed"):
            PypdfTextExtractor(module=Module(error=RuntimeError("malformed"))).extract(
                b"%PDF-bad", artifact)
        for bounds in ((0, 100), (10, 0), (True, 100), (10, 20)):
            with self.subTest(bounds=bounds), self.assertRaisesRegex(ValueError, "positive integers"):
                PypdfTextExtractor(*bounds, module=Module())

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
