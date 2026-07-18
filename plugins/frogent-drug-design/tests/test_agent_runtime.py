"""Behavior tests for the app-facing Codex research runtime."""

import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import date, datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from frogent_plugin.app_v4_bridge import AppV4ResearchManager  # noqa: E402
from frogent_plugin.codex_client import CodexClient  # noqa: E402
from frogent_plugin.codex_roles import CodexPlanner, CodexReader, CodexScreener, CodexSynthesizer  # noqa: E402
from frogent_plugin.codex_schemas import memory_answer_schema  # noqa: E402
from frogent_plugin.conversation_memory import (  # noqa: E402
    ConversationMemoryStore, ConversationTurn,
)
from frogent_plugin.cross_chat_memory import CrossChatMemory  # noqa: E402
from frogent_plugin.contracts import ArtifactRef, ExecutionContext  # noqa: E402
from frogent_plugin.evidence import EvidenceExcerpt, EvidenceStrength, LiteratureRecord, SearchPlan  # noqa: E402
from frogent_plugin.harness import HarnessPolicy  # noqa: E402
from frogent_plugin.literature import LiteratureBatch  # noqa: E402
from frogent_plugin.research_expansion import ExpansionPolicy, ResearchExpander  # noqa: E402
from frogent_plugin.research_factory import OAFallbackResolver, RuntimeConfig, build_research_service  # noqa: E402
from frogent_plugin.research_memory import ResearchMemory, SQLiteResearchStore  # noqa: E402
from frogent_plugin.memory_answer import CodexMemoryAnswerer  # noqa: E402
from frogent_plugin.reader_text import pack_reader_text  # noqa: E402
from frogent_plugin.research_screening import HybridScreener  # noqa: E402
from frogent_plugin.research_service import ResearchService  # noqa: E402
from frogent_plugin.research_types import (  # noqa: E402
    FullTextDocument, ReaderClaim, ReaderReport, ResearchQuery, ResearchRequest,
    ScreeningAssessment, ReaderTask, WorkflowCheckpoint,
)
from frogent_plugin.research_workflow import ResearchController  # noqa: E402


class FakeRunner:
    def __init__(self, outputs):
        self.outputs, self.calls, self.schemas, self.schema_paths = list(outputs), [], [], []
    def __call__(self, args, prompt, timeout, cwd):
        self.calls.append((tuple(args), prompt, timeout, cwd))
        if "--output-schema" in args:
            path = Path(args[args.index("--output-schema") + 1])
            self.schema_paths.append(path)
            self.schemas.append(json.loads(path.read_text()))
        value = self.outputs.pop(0)
        if isinstance(value, Exception): raise value
        return value


def record(record_id="1", source="europe_pmc"):
    return LiteratureRecord(record_id, "p", source, "LRRK2 study", datetime.now(timezone.utc),
                            {"pmid": record_id, "doi": "10.1/" + record_id}, ArtifactRef("a-" + record_id, "raw", "application/json",
                            "memory://" + record_id), date(2020, 1, 1), "abstract")


class AgentRuntimeTests(unittest.TestCase):
    def client(self, outputs):
        runner = FakeRunner(outputs)
        return CodexClient(ROOT, runner=runner, timeout=7), runner

    def test_codex_roles_use_safe_medium_ephemeral_read_only_and_validate_json(self):
        self.assertIsNone(CodexClient(ROOT, runner=FakeRunner([])).timeout)
        with patch("frogent_plugin.codex_client.subprocess.run") as subprocess_run:
            subprocess_run.return_value = type("Completed", (), {"returncode": 0, "stdout": "{}",
                                                   "stderr": ""})()
            CodexClient(ROOT).generate("test role", "empty object", {})
            self.assertIsNone(subprocess_run.call_args.kwargs["timeout"])
        planner_json = {"plan_id": "p", "question": "LRRK2?", "as_of": "2024-12-31",
                        "queries": [{"capability_id": "europe-pmc.search", "source": "europe_pmc",
                                     "wave": "discovery", "query": "LRRK2 Parkinson", "limit": 5}],
                        "inclusion_criteria": ["mechanistic evidence"], "exclusion_criteria": ["unrelated"],
                        "stop_rules": ["anchor and challenge complete"], "knowledge_candidates": []}
        client, runner = self.client([json.dumps(planner_json)])
        request = CodexPlanner(client, ("europe_pmc",)).plan("LRRK2?", date(2024, 12, 31),
                                                             ExecutionContext("u", "c", "j", ROOT))
        args, prompt, timeout, cwd = runner.calls[0]
        self.assertEqual("LRRK2?", request.plan.question)
        self.assertIn("gpt-5.6-sol", args)
        self.assertIn("model_reasoning_effort=\"medium\"", args)
        self.assertIn("--ephemeral", args)
        self.assertIn("--ignore-user-config", args)
        self.assertIn("--output-schema", args)
        self.assertEqual("read-only", args[args.index("--sandbox") + 1])
        self.assertNotIn("LRRK2?", args)
        self.assertEqual((7, ROOT.resolve()), (timeout, cwd))
        self.assertIn("JSON", prompt)
        schema = runner.schemas[0]
        query_schema = schema["properties"]["queries"]["items"]
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(1, query_schema["properties"]["limit"]["minimum"])
        self.assertEqual(10, query_schema["properties"]["limit"]["maximum"])
        self.assertIn("discovery", query_schema["properties"]["wave"]["enum"])
        self.assertNotIn("uniqueItems", json.dumps(schema))
        self.assertFalse(runner.schema_paths[0].exists())
        with self.assertRaisesRegex(ValueError, "inside plugin root"):
            client.generate("test", "empty", {}, cwd=ROOT.parent)
        malformed, _ = self.client(["not-json"])
        with self.assertRaisesRegex(ValueError, "valid JSON"):
            CodexPlanner(malformed, ("europe_pmc",)).plan("x", date.today(),
                                                           ExecutionContext("u", "c", "j2", ROOT))
        failed, failed_runner = self.client([RuntimeError("model failed")])
        with self.assertRaisesRegex(RuntimeError, "model failed"):
            CodexPlanner(failed, ("europe_pmc",)).plan("x", date.today(),
                                                        ExecutionContext("u", "c", "j3", ROOT))
        self.assertFalse(failed_runner.schema_paths[0].exists())

    def test_planner_query_result_cap_fails_before_retrieval(self):
        output = {"plan_id": "p", "question": "Q", "as_of": "2024-12-31",
                  "queries": [{"capability_id": "europe-pmc.search", "source": "europe_pmc",
                               "wave": "discovery", "query": "Q", "limit": 11}],
                  "inclusion_criteria": ["relevant"], "exclusion_criteria": ["unrelated"],
                  "stop_rules": ["complete"], "knowledge_candidates": []}
        client, _ = self.client([json.dumps(output)])
        with self.assertRaisesRegex(ValueError, "query route or limit"):
            CodexPlanner(client, ("europe_pmc",), max_results_per_query=10).plan(
                "Q", date(2024, 12, 31), ExecutionContext("u", "c", "cap", ROOT))

    def test_reader_screener_and_synthesizer_are_typed_and_fail_closed(self):
        reader_json = {"task_id": "reader-1", "family_id": "pmid:1", "record_id": "1",
                       "claims": [{"statement": "LRRK2 phosphorylates Rab", "locator": "abstract:1",
                                   "population_or_model": "cells", "intervention": "LRRK2",
                                   "comparator": "control", "outcome": "Rab phosphorylation",
                                   "direction": "support", "magnitude": "reported", "limitations": ["in vitro"]}],
                       "counterevidence": False, "integrity_status": "clear",
                       "limitations": ["model"], "unresolved_questions": ["human relevance"]}
        screening_json = {"outcome": "include", "reasons": ["direct structured claim"], "strength": "moderate"}
        synthesis_json = {"source_study_answer": "The study supports the claim.",
                          "current_evidence_update": "Later evidence is mixed.",
                          "citations": ["ev-1"], "counterevidence": ["ev-2"],
                          "gaps": ["no clinical endpoint"], "limitations": ["cell model"]}
        client, runner = self.client([json.dumps(reader_json), json.dumps(screening_json), json.dumps(synthesis_json)])
        task = ReaderTask("reader-1", "pmid:1", record(), None, "FULL TEXT")
        report = CodexReader(client).read(task)
        self.assertIn("Compare publication enrollment, design, and outcomes", runner.calls[0][1])
        self.assertIn("not observed efficacy or safety results", runner.calls[0][1])
        assessment = CodexScreener(client).assess(report, task.record)
        evidence = (EvidenceExcerpt("ev-1", "1", "claim", "abstract:1", EvidenceStrength.MODERATE),
                    EvidenceExcerpt("ev-2", "1", "counter", "abstract:2", EvidenceStrength.LOW))
        answer = CodexSynthesizer(client).synthesize("question", evidence, (report,), ("gap",))
        self.assertEqual(("include", EvidenceStrength.MODERATE), (assessment.outcome, assessment.strength))
        self.assertIn("Source-study answer", answer)
        self.assertEqual(3, len(runner.schemas))
        synthesis_schema = runner.schemas[-1]
        self.assertEqual(["ev-1", "ev-2"],
                         synthesis_schema["properties"]["citations"]["items"]["enum"])
        self.assertTrue(all(not item["additionalProperties"] for item in runner.schemas))
        self.assertTrue(all(not path.exists() for path in runner.schema_paths))
        bad, _ = self.client([json.dumps({**reader_json, "unexpected": True})])
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            CodexReader(bad).read(task)
        malformed = {**synthesis_json, "unexpected": True}
        bad_synth, bad_runner = self.client([json.dumps(malformed), json.dumps(synthesis_json)])
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            CodexSynthesizer(bad_synth).synthesize("question", evidence, (report,), ())
        self.assertEqual(1, len(bad_runner.calls))

    def test_reader_text_packing_retains_late_structured_evidence_and_balanced_boundaries(self):
        structured = "\n".join((
            "[TITLE] A structured paper",
            "[ABSTRACT 1 P1] Concise abstract evidence.",
            "[SECTION 1 Methods P1] " + "method noise " * 1000 + "METHOD-END",
            "[SECTION 2 Results P1] Late measured result survives.",
            "[SECTION 3 Discussion P1] Late limiting interpretation survives.",
            "[SECTION 4 Correction P1] Corrected value and caveat survives.",
        ))
        packed = pack_reader_text(structured, 440)
        self.assertLessEqual(len(packed), 440)
        for value in ("[TITLE]", "[ABSTRACT", "[SECTION 2 Results P1]",
                      "[SECTION 3 Discussion P1]", "[SECTION 4 Correction P1]"):
            self.assertIn(value, packed)
        self.assertNotIn("METHOD-END", packed)
        unstructured = "HEAD-EVIDENCE " + "middle " * 500 + " TAIL-COUNTEREVIDENCE"
        balanced = pack_reader_text(unstructured, 180)
        self.assertEqual(180, len(balanced))
        self.assertIn("HEAD-EVIDENCE", balanced)
        self.assertIn("TAIL-COUNTEREVIDENCE", balanced)
        self.assertIn("[OMITTED MIDDLE]", balanced)

        output = {"task_id": "reader-1", "family_id": "pmid:1", "record_id": "1",
                  "claims": [{"statement": "claim", "locator": "Results P1",
                              "population_or_model": "model", "intervention": "drug",
                              "comparator": "control", "outcome": "outcome",
                              "direction": "support", "magnitude": "reported", "limitations": []}],
                  "counterevidence": False, "integrity_status": "clear",
                  "limitations": [], "unresolved_questions": []}
        client, runner = self.client([json.dumps(output)])
        task = ReaderTask("reader-1", "pmid:1", record(), None, structured)
        CodexReader(client, max_chars=440).read(task)
        prompt = runner.calls[0][1]
        self.assertIn("Late measured result survives", prompt)
        self.assertIn("Late limiting interpretation survives", prompt)
        self.assertIn("Corrected value and caveat survives", prompt)
        self.assertNotIn("METHOD-END", prompt)

    def test_synthesizer_dynamic_binding_empty_evidence_and_single_repair(self):
        valid = {"source_study_answer": "Bounded answer", "current_evidence_update": "Current update",
                 "citations": ["ev-1"], "counterevidence": [], "gaps": [], "limitations": []}
        fabricated = {**valid, "citations": ["ev-fabricated"]}
        evidence = (EvidenceExcerpt("ev-1", "1", "verified claim", "abstract:1",
                                    EvidenceStrength.MODERATE),)
        client, runner = self.client([json.dumps(fabricated), json.dumps(valid)])
        answer = CodexSynthesizer(client).synthesize("Q", evidence, (), ())
        self.assertIn("ev-1", answer)
        self.assertNotIn("ev-fabricated", answer)
        self.assertEqual(2, len(runner.calls))
        self.assertIn('"validation_error"', runner.calls[1][1])
        self.assertIn('"previous_output"', runner.calls[1][1])
        self.assertIn('"allowed_evidence_ids": ["ev-1"]', runner.calls[1][1])
        self.assertEqual(runner.schemas[0], runner.schemas[1])
        empty = {**valid, "citations": [], "counterevidence": []}
        empty_client, empty_runner = self.client([json.dumps(empty)])
        empty_answer = CodexSynthesizer(empty_client).synthesize("Q", (), (), ())
        self.assertIn("Citations: none", empty_answer)
        self.assertEqual(0, empty_runner.schemas[0]["properties"]["citations"]["maxItems"])
        self.assertEqual(1, len(empty_runner.calls))

    def test_failed_synthesis_repair_preserves_partial_checkpoint_and_telemetry(self):
        fabricated = {"source_study_answer": "Unsafe", "current_evidence_update": "Unsafe",
                      "citations": ["ev-fabricated"], "counterevidence": [],
                      "gaps": [], "limitations": []}
        client, runner = self.client([json.dumps(fabricated), json.dumps(fabricated)])
        class Provider:
            def search(self, query, context): return LiteratureBatch(query, (record("1"),), "fake")
        class Reader:
            def read(self, task):
                claim = ReaderClaim("verified claim", "abstract:1", "cells", "drug", "control",
                                    "outcome", "support", "reported")
                return ReaderReport(task.task_id, task.family_id, task.record.id, (claim,), False,
                                    "clear", (), ())
        class Screener:
            def assess(self, report, item):
                return ScreeningAssessment("include", ("qualified",), EvidenceStrength.MODERATE)
        class Planner:
            def plan(self, question, as_of, context, history=()):
                plan = SearchPlan("p", question, as_of, ("Q",), ("europe_pmc",),
                                  ("relevant",), ("unrelated",), ("complete",))
                return ResearchRequest(plan, (ResearchQuery("europe-pmc.search", "europe_pmc", "Q"),))
        ticks = iter((0.0, 1.0))
        controller = ResearchController({"europe-pmc.search": Provider()}, {}, Reader(),
            CodexSynthesizer(client), HarnessPolicy(max_tool_calls=2), screener=Screener(),
            clock=lambda: next(ticks))
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            store = SQLiteResearchStore(Path(temp) / "memory.sqlite3", ROOT)
            service = ResearchService(Planner(), controller, store, ROOT,
                                      clock=lambda: date(2024, 12, 31))
            frames = tuple(service.stream_payload("u", {"message": "Q", "chat_id": "c", "files": []}))
            saved = store.load("u", "c")
        answer = "".join(frames)
        self.assertIn("Evidence-bounded partial synthesis", answer)
        self.assertIn("[ev-1] verified claim", answer)
        self.assertNotIn("ev-fabricated", answer)
        self.assertEqual(2, len(runner.calls))
        self.assertEqual((1, 1, 1.0), (saved.checkpoint.provider_calls,
                                      saved.checkpoint.reader_tasks, saved.checkpoint.elapsed_seconds))
        self.assertEqual(("1",), tuple(item.record_id for item in saved.checkpoint.hits))
        self.assertEqual(("reader-1",), tuple(item.task_id for item in saved.checkpoint.reports))
        self.assertEqual(("ev-1",), tuple(item["id"] for item in saved.admitted_evidence))
        self.assertTrue(any("synthesis unavailable after bounded recovery" in gap
                            for gap in saved.checkpoint.coverage_gaps))
        error = next(item for item in service.typed_events[("u", "c")] if item.kind == "error")
        self.assertEqual(("synthesis", True), (error.payload["stage"], error.payload["recoverable"]))

    def test_sqlite_memory_is_atomic_resumable_isolated_and_revocable(self):
        planner_json = {"plan_id": "p", "question": "Q", "as_of": "2024-12-31",
                        "queries": [{"capability_id": "europe-pmc.search", "source": "europe_pmc",
                                     "wave": "discovery", "query": "Q", "limit": 3}],
                        "inclusion_criteria": ["relevant"], "exclusion_criteria": ["unrelated"],
                        "stop_rules": ["complete"],
                        "knowledge_candidates": []}
        client, _ = self.client([json.dumps(planner_json)])
        request = CodexPlanner(client, ("europe_pmc",)).plan("Q", date(2024, 12, 31),
                                                             ExecutionContext("u", "c", "j", ROOT))
        checkpoint = WorkflowCheckpoint(("europe-pmc.search|europe_pmc|Q",), (record(),),
                                        revoked_record_ids=("1",))
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            store = SQLiteResearchStore(Path(temp) / "memory.sqlite3", ROOT)
            state = ResearchMemory(request, checkpoint, ({"id": "ev-1", "record_id": "1"},),
                                   ("answer-v1",), ("1",))
            store.save("u", "c", state)
            loaded = store.load("u", "c")
            self.assertEqual(checkpoint.completed_queries, loaded.checkpoint.completed_queries)
            self.assertEqual(("1",), loaded.revocations)
            self.assertIsNone(store.load("u", "other"))
            store.save("other-user", "c", state)
            store.delete("u", "c")
            self.assertIsNone(store.load("u", "c"))
            self.assertIsNotNone(store.load("other-user", "c"))
        with self.assertRaisesRegex(ValueError, "inside plugin root"):
            SQLiteResearchStore(ROOT.parent / "memory.sqlite3", ROOT)

    def test_expansion_is_bounded_deduplicated_and_keeps_optional_failures_as_gaps(self):
        class Europe:
            def related(self, source, identifier, relation, limit):
                if relation == "references": raise TimeoutError("reference timeout")
                return ("2", "2", "3")
        class OpenAlex:
            def expand_work(self, doi): raise RuntimeError("openalex unavailable")
        item = record()
        expander = ResearchExpander(Europe(), OpenAlex(), ExpansionPolicy(max_queries=4, related_limit=5))
        leads = ({"name": "Ada Author", "orcid": "0000-0001"},
                 {"name": "Ada Author", "orcid": "0000-0001"})
        batch = expander.expand((item,), leads)
        self.assertLessEqual(len(batch.queries), 4)
        self.assertEqual(len({query.query for query in batch.queries}), len(batch.queries))
        self.assertTrue(any("reference timeout" in gap for gap in batch.gaps))
        self.assertTrue(any("openalex unavailable" in gap for gap in batch.gaps))
        self.assertTrue(all(query.wave == "expansion" for query in batch.queries))

    def test_expansion_stops_network_calls_when_query_cap_is_full(self):
        class Europe:
            def __init__(self): self.calls = []
            def related(self, source, identifier, relation, limit):
                self.calls.append((identifier, relation))
                return ("same-related",)
        class OpenAlex:
            def __init__(self): self.calls = []
            def expand_work(self, doi):
                self.calls.append(doi)
                return {"authors": ({"author": "Author One"}, {"author": "Author Two"})}
        europe, openalex = Europe(), OpenAlex()
        values = tuple(record(str(index)) for index in range(8))
        batch = ResearchExpander(europe, openalex, ExpansionPolicy(max_queries=3)).expand(values, ())
        self.assertEqual((2, 1, 3), (len(europe.calls), len(openalex.calls), len(batch.queries)))
        self.assertEqual(("citations:0", "openalex-author:0", "openalex-author:0"),
                         tuple(item.provenance for item in batch.queries))
        europe2, openalex2 = Europe(), OpenAlex()
        leads = ({"name": "A", "orcid": "1"}, {"name": "B", "orcid": "2"})
        author_only = ResearchExpander(europe2, openalex2, ExpansionPolicy(max_queries=2)).expand(values, leads)
        self.assertEqual((0, 0, 2), (len(europe2.calls), len(openalex2.calls), len(author_only.queries)))

    def test_app_v4_payload_streams_answer_and_reuses_persistent_checkpoint(self):
        class Planner:
            calls = 0
            histories = []
            def plan(self, question, as_of, context, history=()):
                self.calls += 1
                self.histories.append(tuple(history))
                plan = SearchPlan("p", question, as_of, ("Q",), ("europe_pmc",), ("relevant",),
                                  ("unrelated",), ("complete",))
                return ResearchRequest(plan, (ResearchQuery("europe-pmc.search", "europe_pmc", "Q"),))
        class Controller:
            checkpoints = []
            def run(self, request, context, checkpoint=None, revoked_record_ids=()):
                self.checkpoints.append(checkpoint)
                saved = WorkflowCheckpoint(("done",), (), revoked_record_ids=tuple(revoked_record_ids))
                return type("Result", (), {"answer": "source answer", "checkpoint": saved,
                    "ledger": type("Ledger", (), {"admitted": lambda self: ()})(),
                    "coverage_gaps": (), "events": (), "working_memory_ids": ()})()
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            store = SQLiteResearchStore(Path(temp) / "memory.sqlite3", ROOT)
            planner, controller = Planner(), Controller()
            service = ResearchService(planner, controller, store, ROOT)
            payload = {"message": "Q", "chat_id": "chat", "files": []}
            frames = tuple(service.stream_payload("user", payload, history=[]))
            self.assertTrue(any('"content": "source answer"' in frame for frame in frames))
            self.assertTrue(any('"stop": true' in frame for frame in frames))
            self.assertEqual("data: [DONE]\n\n", frames[-1])
            tuple(service.stream_payload("user", payload, history=[]))
            self.assertEqual(1, planner.calls)
            self.assertIsNotNone(controller.checkpoints[-1])
            followup = {**payload, "message": "What are the limitations?"}
            tuple(service.stream_payload("user", followup, history=[]))
            self.assertEqual(2, planner.calls)
            self.assertTrue(any(item.get("content") == "source answer" for item in planner.histories[-1]))
            self.assertEqual(["user", "assistant"], [item["role"] for item in planner.histories[-1]])
            self.assertEqual(4, len(store.load("user", "chat").conversation_context))
            tuple(service.stream_payload("user", {**payload, "chat_id": "other"}, history=[]))
            self.assertEqual(3, planner.calls)
            self.assertTrue(all("FULL TEXT" not in frame for frame in frames))
            for index in range(10):
                tuple(service.stream_payload("user", {**payload, "message": f"follow-up {index}"}, history=[]))
            bounded = store.load("user", "chat")
            self.assertEqual((8, 8), (len(bounded.answer_versions), len(bounded.conversation_context)))

    def test_factory_is_directly_configurable_and_keeps_optional_routes_as_gaps(self):
        planner_json = {"plan_id": "p", "question": "Q", "as_of": "2024-12-31",
                        "queries": [{"capability_id": "europe-pmc.search", "source": "europe_pmc",
                                     "wave": "discovery", "query": "Q", "limit": 2}],
                        "inclusion_criteria": ["relevant"], "exclusion_criteria": ["unrelated"],
                        "stop_rules": ["complete"], "knowledge_candidates": []}
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            relative = str(Path(temp).relative_to(ROOT) / "memory.sqlite3")
            executable = str(ROOT / ".runtime" / "codex-new")
            memory_json = {"answer": "Your saved preference is concise reports.",
                           "supporting_memory_ids": ["memory:past:preference"], "abstain": False}
            runner = FakeRunner([json.dumps(planner_json), json.dumps(memory_json)])
            with patch.dict("os.environ", {"FROGENT_MEMORY_DB": relative,
                                            "FROGENT_CODEX_EXECUTABLE": executable}, clear=True):
                config = RuntimeConfig.from_env(ROOT)
                service = build_research_service(config, runner=runner)
            service.planner.plan("Q", date(2024, 12, 31), ExecutionContext("u", "c", "j", ROOT))
            self.assertIsInstance(service, ResearchService)
            self.assertEqual(executable, runner.calls[0][0][0])
            self.assertIsNone(runner.calls[0][2])
            self.assertEqual(("europe_pmc",), service.planner.routes)
            self.assertEqual((10, 6), (config.max_results_per_query, config.max_reader_documents))
            self.assertIsInstance(service.controller.screener, HybridScreener)
            self.assertEqual("ClinicalTrialsResolver",
                             type(service.controller.registry_resolver).__name__)
            self.assertIsNone(service.controller.registry_resolver.transport.timeout)
            gaps = service.controller.configuration_gaps
            self.assertTrue(any("PubMed unavailable" in gap for gap in gaps))
            self.assertTrue(any("OPENALEX_API_KEY" in gap for gap in gaps))
            self.assertTrue(any("UNPAYWALL_EMAIL" in gap for gap in gaps))
            service.ingest_memory_session("benchmark-user", "past", (
                ConversationTurn("preference", "user", "I prefer concise reports.",
                                 "2024-01-01T00:00:00+00:00"),))
            service.controller = type("NeverController", (), {
                "run": lambda self, *args, **kwargs: (_ for _ in ()).throw(
                    AssertionError("literature controller must not run"))})()
            memory_result = service.ask_memory("benchmark-user", "fresh-final",
                                               "What reports do I prefer?",
                                               occurred_at="2025-01-01T00:00:00+00:00")
            self.assertEqual(("fresh-final", False),
                             (memory_result.conversation_id, memory_result.abstain))
            self.assertNotIn('"session_id": "fresh-final"', runner.calls[1][1])
            self.assertEqual(3, service.memory_store.count("benchmark-user"))
            with patch.dict("os.environ", {"FROGENT_MEMORY_DB": relative,
                            "FROGENT_CODEX_TIMEOUT": "31",
                            "FROGENT_MAX_RESULTS_PER_QUERY": "7",
                            "FROGENT_MAX_READER_DOCUMENTS": "5"}, clear=True):
                tuned = RuntimeConfig.from_env(ROOT)
            self.assertEqual((31, 7, 5), (tuned.codex_timeout, tuned.max_results_per_query,
                                         tuned.max_reader_documents))
            for disabled in ("", "   ", "0", "0.0"):
                with self.subTest(timeout=disabled), patch.dict("os.environ", {
                        "FROGENT_MEMORY_DB": relative, "FROGENT_CODEX_TIMEOUT": disabled}, clear=True):
                    self.assertIsNone(RuntimeConfig.from_env(ROOT).codex_timeout)
            for invalid in ("-1", "nan", "inf", "-inf", "invalid"):
                with self.subTest(timeout=invalid), patch.dict("os.environ", {
                        "FROGENT_MEMORY_DB": relative, "FROGENT_CODEX_TIMEOUT": invalid}, clear=True):
                    with self.assertRaisesRegex(ValueError, "positive finite"):
                        RuntimeConfig.from_env(ROOT)
            self.assertIsNone(CodexClient(ROOT, runner=FakeRunner([]), timeout=0).timeout)
            for invalid in (-1, float("nan"), float("inf")):
                with self.assertRaisesRegex(ValueError, "positive finite"):
                    CodexClient(ROOT, runner=FakeRunner([]), timeout=invalid)

    def test_factory_uses_installed_pypdf_reports_missing_and_honors_injection(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp, patch.dict(
                "os.environ", {}, clear=True):
            def config(name):
                return RuntimeConfig(ROOT, Path(temp) / f"{name}.sqlite3")

            installed = object()
            with patch("frogent_plugin.research_factory.PypdfTextExtractor",
                       return_value=installed) as constructor:
                service = build_research_service(config("installed"), runner=FakeRunner([]))
            self.assertEqual(1, constructor.call_count)
            resolver = service.controller.resolvers["europe_pmc"].repository
            self.assertIs(installed, resolver.extractor)
            self.assertFalse(any("pypdf" in gap for gap in service.controller.configuration_gaps))

            missing = ModuleNotFoundError("No module named 'pypdf'")
            with patch("frogent_plugin.research_factory.PypdfTextExtractor", side_effect=missing):
                service = build_research_service(config("missing"), runner=FakeRunner([]))
            resolver = service.controller.resolvers["europe_pmc"].repository
            self.assertIsNone(resolver.extractor)
            self.assertTrue(any("pypdf>=6,<7 is not installed" in gap
                                for gap in service.controller.configuration_gaps))

            explicit = object()
            with patch("frogent_plugin.research_factory.PypdfTextExtractor",
                       side_effect=AssertionError("default extractor must not be constructed")):
                service = build_research_service(config("explicit"), runner=FakeRunner([]),
                                                 pdf_extractor=explicit)
            resolver = service.controller.resolvers["europe_pmc"].repository
            self.assertIs(explicit, resolver.extractor)

    def test_all_hits_are_preserved_while_reader_cap_uses_first_hit_order(self):
        identifiers = ("z", "a", "y", "b", "x", "c") + tuple(f"r{index:02d}" for index in range(14))
        records = tuple(record(value) for value in identifiers)
        class Provider:
            def search(self, query, context): return LiteratureBatch(query, records, "fake")
        class Resolver:
            def __init__(self): self.calls = []
            def resolve(self, item, context): self.calls.append(item.id); return None
        class Reader:
            def read(self, task):
                claim = ReaderClaim("claim", "abstract:1", "cells", "drug", "control",
                                    "outcome", "support", "reported")
                return ReaderReport(task.task_id, task.family_id, task.record.id, (claim,), False,
                                    "clear", (), ())
        class Synthesizer:
            def synthesize(self, question, evidence, reports, gaps): return "bounded"
        resolver = Resolver()
        plan = SearchPlan("p", "Q", date(2024, 12, 31), ("Q",), ("europe_pmc",),
                          ("relevant",), ("unrelated",), ("complete",))
        request = ResearchRequest(plan, (ResearchQuery("europe-pmc.search", "europe_pmc", "Q", 20),))
        controller = ResearchController({"europe-pmc.search": Provider()}, {"europe_pmc": resolver},
            Reader(), Synthesizer(), HarnessPolicy(max_tool_calls=2), max_reader_documents=6)
        result = controller.run(request, ExecutionContext("u", "c", "bounded", ROOT))
        self.assertEqual(identifiers, tuple(item.id for item in result.raw_records))
        self.assertEqual(identifiers, tuple(item.record_id for item in result.hits))
        self.assertEqual(6, len(resolver.calls))
        self.assertCountEqual(identifiers[:6], resolver.calls)
        self.assertEqual(identifiers[:6], tuple(item.record_id for item in result.reader_reports))
        self.assertEqual((20, 6, 6), (len(result.raw_records), len(result.reader_reports),
                                     result.telemetry.reader_tasks))
        self.assertTrue(any("reader document cap omitted 14 records" in gap for gap in result.coverage_gaps))

    def test_hybrid_screener_delegates_only_uncertain_and_controls_memory(self):
        values = tuple(record(value) for value in ("clear", "retracted", "uncertain"))
        class Provider:
            def search(self, query, context): return LiteratureBatch(query, values, "fake")
        class Reader:
            def read(self, task):
                claim = ReaderClaim("claim", "abstract:1", "cells", "drug", "control",
                                    "outcome", "support", "reported")
                return ReaderReport(task.task_id, task.family_id, task.record.id, (claim,), False,
                                    task.record.id, (), ())
        class Delegate:
            def __init__(self): self.calls = []
            def assess(self, report, item):
                self.calls.append(item.id)
                return ScreeningAssessment("include", ("Codex resolved ambiguity",), EvidenceStrength.MODERATE)
        class Synthesizer:
            def synthesize(self, question, evidence, reports, gaps): return "screened"
        delegate = Delegate()
        hybrid = HybridScreener(delegate)
        plan = SearchPlan("p", "Q", date(2024, 12, 31), ("Q",), ("europe_pmc",),
                          ("relevant",), ("unrelated",), ("complete",))
        request = ResearchRequest(plan, (ResearchQuery("europe-pmc.search", "europe_pmc", "Q"),))
        result = ResearchController({"europe-pmc.search": Provider()}, {}, Reader(), Synthesizer(),
            HarnessPolicy(max_tool_calls=2), screener=hybrid).run(
                request, ExecutionContext("u", "c", "screen", ROOT))
        self.assertEqual(["uncertain"], delegate.calls)
        self.assertEqual({"ev-clear", "ev-uncertain"}, set(result.working_memory_ids))
        self.assertFalse(result.ledger.has_admitted("ev-retracted"))

    def test_app_v4_manager_preserves_call_identity_payload_history_and_sse(self):
        class Service:
            calls = []
            frames = ("data: {\"content\": \"answer\", \"name\": \"research\"}\n\n",
                      "data: [DONE]\n\n")
            def stream_payload(self, user_id, payload, *, history=()):
                self.calls.append((user_id, payload, history))
                return iter(self.frames)
        seen_users, service = [], Service()
        def conversation(user_id):
            seen_users.append(user_id)
            return "chat-42"
        manager = AppV4ResearchManager(service, conversation)
        history = [{"content": "prior", "isUser": True}]
        text_frames = tuple(manager.chat_stream("user-7", "LRRK2?", history))
        file_frames = tuple(manager.chat_stream("user-7",
                            [{"text": "Read this"}, {"file": "/uploads/paper.pdf"}], history))
        self.assertEqual(Service.frames, text_frames)
        self.assertEqual(Service.frames, file_frames)
        self.assertEqual(["user-7", "user-7"], seen_users)
        self.assertEqual(("user-7", "chat-42", "LRRK2?", [], history),
                         (service.calls[0][0], service.calls[0][1]["chat_id"],
                          service.calls[0][1]["message"], service.calls[0][1]["files"],
                          service.calls[0][2]))
        self.assertEqual([{"path": "/uploads/paper.pdf"}], service.calls[1][1]["files"])

    def test_controller_store_resume_expansion_revocation_and_full_text_isolation(self):
        class Provider:
            def __init__(self): self.calls, self.related_calls = [], 0
            def search(self, query, context):
                self.calls.append(query.query)
                values = (record("1"),) if query.query == "anchor" else (record("2"),)
                return LiteratureBatch(query, values, "fake")
            def related(self, source, identifier, relation, limit):
                self.related_calls += 1
                return ("2",)
            def metadata(self, record_id): return {}
        class Resolver:
            def resolve(self, item, context):
                return FullTextDocument(item.id, ArtifactRef("oa-" + item.id, "oa", "text/plain",
                                        "memory://oa/" + item.id), "FULL TEXT PRIVATE " + item.id)
        class Reader:
            def read(self, task):
                claim = ReaderClaim("claim " + task.record.id, "section:1", "cells", "drug", "control",
                                    "outcome", "support", "reported")
                return ReaderReport(task.task_id, task.family_id, task.record.id, (claim,), False,
                                    "clear", (), ())
        class Screener:
            def assess(self, report, item): return ScreeningAssessment("include", ("qualified",))
        class Synthesizer:
            def synthesize(self, question, evidence, reports, gaps):
                return "admitted=" + ",".join(item.id for item in evidence)
        class Planner:
            def __init__(self): self.calls = 0
            def plan(self, question, as_of, context, history=()):
                self.calls += 1
                plan = SearchPlan("p", question, as_of, ("anchor",), ("europe_pmc",),
                                  ("relevant",), ("unrelated",), ("complete",))
                return ResearchRequest(plan, (ResearchQuery("europe-pmc.search", "europe_pmc", "anchor"),))
        provider, planner = Provider(), Planner()
        ticks = iter(range(20))
        expander = ResearchExpander(provider, policy=ExpansionPolicy(
            max_queries=2, include_authors=False, include_references=False))
        controller = ResearchController({"europe-pmc.search": provider}, {"europe_pmc": Resolver()}, Reader(),
                                        Synthesizer(), HarnessPolicy(max_tool_calls=8), screener=Screener(),
                                        expander=expander, clock=lambda: next(ticks))
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            path = Path(temp) / "memory.sqlite3"
            store = SQLiteResearchStore(path, ROOT)
            service = ResearchService(planner, controller, store, ROOT, clock=lambda: date(2024, 12, 31))
            payload = {"message": "Q", "chat_id": "chat", "files": [{"path": "ignored"}]}
            first = tuple(service.stream_payload("u", payload, history=[{"content": "prior"}]))
            self.assertEqual(["anchor", "EXT_ID:2"], provider.calls)
            self.assertIn("ev-1", "".join(first))
            self.assertNotIn(b"FULL TEXT PRIVATE", path.read_bytes())
            saved = store.load("u", "chat")
            self.assertEqual(("expansion",), tuple(item.wave for item in saved.checkpoint.expansion_queries))
            self.assertEqual(("citations:1",), tuple(item.provenance for item in saved.checkpoint.expansion_queries))
            self.assertEqual([(1, 1, "planned", "1"), (1, 2, "expansion", "2")],
                             [(item.rank, item.occurrence, item.wave, item.record_id)
                              for item in saved.checkpoint.hits])
            self.assertEqual((2, 2, 1.0), (saved.checkpoint.provider_calls,
                                          saved.checkpoint.reader_tasks, saved.checkpoint.elapsed_seconds))
            tuple(service.stream_payload("u", payload, history=[]))
            self.assertEqual(["anchor", "EXT_ID:2"], provider.calls)
            self.assertEqual(1, provider.related_calls)
            before_revoke = store.load("u", "chat").checkpoint
            service.revoke("u", "chat", ("1",))
            revoked = store.load("u", "chat").checkpoint
            self.assertEqual(
                (before_revoke.provider_calls, before_revoke.reader_tasks,
                 before_revoke.elapsed_seconds, before_revoke.hits),
                (revoked.provider_calls, revoked.reader_tasks,
                 revoked.elapsed_seconds, revoked.hits),
            )
            third = tuple(service.stream_payload("u", payload, history=[]))
            self.assertNotIn("ev-1", "".join(third))
            self.assertIn("ev-2", "".join(third))
            self.assertEqual(("1",), store.load("u", "chat").revocations)

    def test_oa_primary_failure_is_visible_with_or_without_successful_fallback(self):
        class Primary:
            def resolve(self, item, context): raise TimeoutError("fullTextXML timeout")
        class Fallback:
            def __init__(self, succeeds): self.succeeds = succeeds
            def resolve(self, item, context):
                if not self.succeeds: raise RuntimeError("fallback unavailable")
                return FullTextDocument(item.id, ArtifactRef("oa", "oa", "text/plain", "memory://oa"), "text")
        context = ExecutionContext("u", "c", "j", ROOT)
        successful = OAFallbackResolver(Primary(), Fallback(True))
        self.assertIsNotNone(successful.resolve(record(), context))
        self.assertIn("fullTextXML timeout", successful.coverage_gap("1"))
        failed = OAFallbackResolver(Primary(), Fallback(False))
        with self.assertRaisesRegex(RuntimeError, "fullTextXML timeout.*fallback unavailable"):
            failed.resolve(record(), context)

    def test_codex_timeout_becomes_sse_error_and_does_not_create_session(self):
        expired = subprocess.TimeoutExpired(["codex", "exec"], 240)
        client, runner = self.client([expired])
        planner = CodexPlanner(client, ("europe_pmc",))
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            store = SQLiteResearchStore(Path(temp) / "memory.sqlite3", ROOT)
            service = ResearchService(planner, object(), store, ROOT)
            frames = tuple(service.stream_payload("u", {"message": "Q", "chat_id": "c", "files": []}))
            error_frame = next(frame for frame in frames if '"error"' in frame)
            self.assertIn("timed out after 240 seconds", error_frame)
            self.assertIn('"error_type": "TimeoutExpired"', error_frame)
            self.assertIn('"name": "research"', error_frame)
            self.assertEqual("data: [DONE]\n\n", frames[-1])
            self.assertIsNone(store.load("u", "c"))
            self.assertEqual("TimeoutExpired",
                             service.typed_events[("u", "c")][0].payload["error_type"])
            self.assertTrue(runner.schema_paths)
            self.assertTrue(all(not path.exists() for path in runner.schema_paths))

    def test_cross_chat_memory_is_cold_resumable_idempotent_ranked_and_user_isolated(self):
        turns = (
            ConversationTurn("t1", "user", "My project codename is Cedar and favorite color is teal.",
                             "2024-01-01T09:00:00+00:00"),
            ConversationTurn("t2", "assistant", "I recommended the compact blue microscope.",
                             "2024-01-01T09:01:00+00:00"),
            ConversationTurn("t3", "user", "My project codename is now Juniper.",
                             "2024-06-01T09:00:00+00:00"),
        )
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            path = Path(temp) / "memory.sqlite3"
            store = ConversationMemoryStore(path, ROOT)
            self.assertEqual(3, store.ingest_session("alice", "chat-old", "session-old", turns))
            self.assertEqual(0, store.ingest_session("alice", "chat-old", "session-old", turns))
            store.ingest_session("bob", "chat-b", "session-b", (
                ConversationTurn("b1", "user", "My project codename is Secret Bob.",
                                 "2025-01-01T00:00:00+00:00"),))
            restarted = ConversationMemoryStore(path, ROOT)
            hits = restarted.retrieve("alice", "What is my project codename?", limit=4)
            self.assertEqual("t3", hits[0].turn_id)
            self.assertEqual({"t3", "t1"}, {item.turn_id for item in hits
                                               if item.provenance == "conversation_turn"})
            context = next(item for item in hits if item.turn_id == "t2")
            self.assertEqual("same_session_context", context.provenance)
            self.assertEqual("t3", restarted.retrieve("alice", "What happened in June 2024?", limit=1)[0].turn_id)
            self.assertTrue(all(item.session_id == "session-old" for item in hits))
            self.assertFalse(any("Secret Bob" in item.content for item in hits))
            mixed = restarted.retrieve("alice", "favorite color microscope", limit=8)
            self.assertEqual({"t1", "t2"}, {item.turn_id for item in mixed
                                             if item.provenance == "conversation_turn"})
            assistant_hit = restarted.retrieve("alice", "Which microscope was recommended?", limit=1)[0]
            self.assertEqual(("assistant", "t2"), (assistant_hit.role, assistant_hit.turn_id))
            bob_hits = restarted.retrieve("bob", "project codename", limit=8)
            self.assertEqual((1, "b1"), (len(bob_hits), bob_hits[0].turn_id))
            self.assertEqual((), restarted.retrieve("alice", "unrelated zeppelin banana"))
            with self.assertRaisesRegex(ValueError, "conflicts"):
                restarted.ingest_session("alice", "chat-old", "session-old", (
                    ConversationTurn("t1", "user", "changed", "2024-01-01T09:00:00+00:00"),))

    def test_memory_answer_is_bounded_strict_and_public_api_avoids_full_history_prompt(self):
        good = {"answer": "Your favorite color is teal.",
                "supporting_memory_ids": ["memory:s1:t1"], "abstain": False}
        client, runner = self.client([json.dumps(good)])
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            store = ConversationMemoryStore(Path(temp) / "memory.sqlite3", ROOT)
            memory = CrossChatMemory(store, CodexMemoryAnswerer(client), max_hits=2,
                                     max_prompt_chars=200)
            memory.ingest_session("u", "s1", (
                ConversationTurn("t1", "user", "My favorite color is teal.",
                                 "2024-01-01T00:00:00+00:00"),), conversation_id="old-chat")
            result = memory.ask("u", "fresh-chat", "What is my favorite color?")
            self.assertEqual((False, ("memory:s1:t1",)),
                             (result.abstain, result.supporting_memory_ids))
            self.assertEqual("fresh-chat", result.conversation_id)
            self.assertEqual(1, len(result.hits))
            self.assertIn("memory_hits", runner.calls[0][1])
            self.assertNotIn("entire_history", runner.calls[0][1])
            self.assertEqual(["memory:s1:t1"], runner.schemas[0]["properties"]
                             ["supporting_memory_ids"]["items"]["enum"])
            self.assertEqual({"answer", "supporting_memory_ids", "abstain"},
                             set(runner.schemas[0]["properties"]))
            self.assertEqual(1, len(runner.calls))
            calls = len(runner.calls)
            absent = memory.ask("u", "fresh-chat", "zeppelin banana")
            self.assertTrue(absent.abstain)
            self.assertEqual(calls, len(runner.calls))
        self.assertEqual(0, memory_answer_schema()["properties"]["supporting_memory_ids"]["maxItems"])
        malformed = {**good, "unexpected": True}
        bad_client, bad_runner = self.client([json.dumps(malformed), json.dumps(good)])
        with self.assertRaisesRegex(ValueError, "fields are invalid"):
            CodexMemoryAnswerer(bad_client).answer("favorite?", result.hits)
        self.assertEqual(1, len(bad_runner.calls))

    def test_memory_answer_repairs_supported_and_accepts_partial_abstention(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            store = ConversationMemoryStore(Path(temp) / "memory.sqlite3", ROOT)
            store.ingest_session("u", "old", "s1", (ConversationTurn("t1", "user",
                "The interval was 17 days.", "2024-01-01T00:00:00+00:00"),))
            hits = store.retrieve("u", "What was the interval?", limit=2)
        inconsistent = {"answer": "It was 17 days.", "supporting_memory_ids": [], "abstain": False}
        supported = {**inconsistent, "supporting_memory_ids": ["memory:s1:t1"]}
        client, runner = self.client([json.dumps(inconsistent), json.dumps(supported)])
        answer = CodexMemoryAnswerer(client).answer("What was the interval?", hits)
        self.assertEqual((False, ("memory:s1:t1",)), (answer.abstain, answer.supporting_memory_ids))
        self.assertEqual(2, len(runner.calls))
        repair_prompt = runner.calls[1][1]
        self.assertIn('"validation_error"', repair_prompt)
        self.assertIn('"previous_output"', repair_prompt)
        self.assertIn('"allowed_memory_ids": ["memory:s1:t1"]', repair_prompt)
        self.assertEqual(runner.schemas[0], runner.schemas[1])
        wrong_abstention = {"answer": "No reliable memory.",
                            "supporting_memory_ids": ["memory:s1:t1"], "abstain": True}
        abstention = {**wrong_abstention, "supporting_memory_ids": []}
        abstain_client, abstain_runner = self.client(
            [json.dumps(wrong_abstention), json.dumps(abstention)])
        repaired = CodexMemoryAnswerer(abstain_client).answer("Unknown detail?", hits)
        self.assertEqual((True, ("memory:s1:t1",)),
                         (repaired.abstain, repaired.supporting_memory_ids))
        self.assertEqual(1, len(abstain_runner.calls))

    def test_memory_retrieval_diversifies_sessions_inflections_and_user_facts(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            store = ConversationMemoryStore(Path(temp) / "memory.sqlite3", ROOT)
            verbose = tuple(ConversationTurn(f"v{index}", "assistant",
                f"A generic explanation of breaks lasting {index + 1} days.",
                f"2024-01-{index + 1:02d}T00:00:00+00:00") for index in range(5))
            store.ingest_session("u", "verbose", "verbose", verbose)
            store.ingest_session("u", "second", "second", (ConversationTurn("duration", "user",
                "My second break lasted 10 day.", "2024-02-01T00:00:00+00:00"),))
            hits = store.retrieve("u", "How many days did the breaks last?", limit=3)
            self.assertEqual({"verbose", "second"}, {item.session_id for item in hits[:2]})
            self.assertIn("duration", {item.turn_id for item in hits})
            store.ingest_session("u", "preferences", "preferences", (
                ConversationTurn("old-pref", "user", "I prefer tea.",
                                 "2024-03-01T00:00:00+00:00"),
                ConversationTurn("new-pref", "user", "I prefer coffee now.",
                                 "2024-06-01T00:00:00+00:00"),
                ConversationTurn("generic", "assistant", "Preferences help personalize recommendations.",
                                 "2024-07-01T00:00:00+00:00")))
            preference = store.retrieve("u", "What is my preference?", limit=3)
            self.assertEqual(("new-pref", "user"), (preference[0].turn_id, preference[0].role))
            store.ingest_session("u", "projects", "projects", (ConversationTurn("lead", "user",
                "I led two projects last year.", "2024-08-01T00:00:00+00:00"),))
            store.ingest_session("u", "projects-current", "projects-current", (
                ConversationTurn("leading", "user", "I am leading three projects this year.",
                                 "2025-08-01T00:00:00+00:00"),))
            project = store.retrieve("u", "How many projects did I lead?", limit=1)[0]
            self.assertEqual(("leading", ("lead", "project", "year")),
                             (project.turn_id, project.matched_terms))
            variants = store.retrieve("u", "How many projects were led?", limit=2)
            self.assertEqual({"lead", "leading"}, {item.turn_id for item in variants})

    def test_memory_retrieval_resists_verbose_distractors_and_preserves_fact_joins(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            store = ConversationMemoryStore(Path(temp) / "memory.sqlite3", ROOT)
            for index in range(6):
                store.ingest_session("u", f"noise-{index}", f"noise-{index}", (
                    ConversationTurn(f"noise-{index}", "assistant",
                        "Any tips for getting some new social media followers during weekend "
                        "breaks lasting many days? Look for broad suggestions and general advice.",
                        f"2024-01-{index + 1:02d}T00:00:00+00:00"),))
            store.ingest_session("u", "duration-a", "duration-a", (ConversationTurn("seven", "user",
                "My first social media break lasted 7 days.",
                "2024-02-01T00:00:00+00:00"),))
            store.ingest_session("u", "duration-b", "duration-b", (ConversationTurn("ten", "user",
                "My second social media break lasted 10 day.",
                "2024-03-01T00:00:00+00:00"),))
            durations = store.retrieve("u", "How many days did both social media breaks last?",
                                       limit=4)
            self.assertEqual({"seven", "ten"}, {item.turn_id for item in durations[:2]})

            for index in range(6):
                store.ingest_session("u", f"hobby-{index}", f"hobby-{index}", (
                    ConversationTurn(f"hobby-{index}", "assistant",
                        "I can suggest some new tips for looking at and getting hobby equipment.",
                        f"2024-04-{index + 1:02d}T00:00:00+00:00"),))
            store.ingest_session("u", "guitar", "guitar", (ConversationTurn("guitar-pref", "user",
                "For a guitar I prefer a compact acoustic model and avoid red finishes.",
                "2024-05-01T00:00:00+00:00"),))
            guitar = store.retrieve("u", "Any tips for looking at a new guitar I could get?", limit=3)
            self.assertEqual(("guitar-pref", "user"), (guitar[0].turn_id, guitar[0].role))

            store.ingest_session("u", "shop", "shop", (
                ConversationTurn("shop-name", "user", "I met friends at Maple Market in Kyoto.",
                                 "2024-06-01T00:00:00+00:00"),
                ConversationTurn("shop-chat", "assistant", "General shopping background. " * 300,
                                 "2024-06-01T00:01:00+00:00"),
                ConversationTurn("shop-coupon", "user", "I redeemed a coupon there.",
                                 "2024-06-01T00:02:00+00:00")))
            for index in range(6):
                store.ingest_session("u", f"coupon-noise-{index}", f"coupon-noise-{index}", (
                    ConversationTurn(f"coupon-noise-{index}", "assistant",
                        "Some general store coupon tips are available.",
                        f"2024-07-{index + 1:02d}T00:00:00+00:00"),))
            coupon = store.retrieve("u", "Which store did I visit before redeeming the coupon?",
                                    limit=8, max_prompt_chars=1000)
            self.assertIn("shop-coupon", {item.turn_id for item in coupon})
            name = next(item for item in coupon if item.turn_id == "shop-name")
            self.assertEqual("same_session_context", name.provenance)
            self.assertEqual(8, len(coupon))

            store.ingest_session("u", "timeline", "timeline", (
                ConversationTurn("tourists", "user", "I met the tourists on Friday.",
                                 "2024-08-02T00:00:00+00:00"),
                ConversationTurn("event-paraphrase", "assistant",
                    "You met tourists and later discussed the event itinerary in detail.",
                    "2024-08-02T00:01:00+00:00"),
                ConversationTurn("jam", "user", "The jam event happened two days later.",
                                 "2024-08-04T00:00:00+00:00")))
            timeline = store.retrieve("u", "Did I meet tourists before or after the jam event?",
                                      limit=2)
            self.assertEqual({"tourists", "jam"}, {item.turn_id for item in timeline})
            self.assertIn("two days later", next(item.content for item in timeline
                                                  if item.turn_id == "jam"))

            store.ingest_session("u", "education", "education", (ConversationTurn("edu", "user",
                "I led three education projects while using the fellowship program.",
                "2024-09-01T00:00:00+00:00"),))
            store.ingest_session("u", "education-noise", "education-noise", (
                ConversationTurn("edu-noise", "assistant",
                    "New education project tips include looking at how teams are leading projects "
                    "and using common planning suggestions.", "2024-10-01T00:00:00+00:00"),))
            education = store.retrieve("u", "How many education projects did I lead and use?", limit=1)
            self.assertEqual(("edu", ("education", "lead", "project", "use")),
                             (education[0].turn_id, education[0].matched_terms))

        preference_output = {"answer": "Choose a compact natural-finish acoustic guitar.",
                             "supporting_memory_ids": ["memory:guitar:guitar-pref"],
                             "abstain": False}
        client, runner = self.client([json.dumps(preference_output)])
        answer = CodexMemoryAnswerer(client).answer(
            "Suggest a guitar that follows all my preferences.", guitar)
        prompt = runner.calls[0][1]
        self.assertIn("preference checklist", prompt)
        self.assertIn("negative constraints", prompt)
        self.assertNotIn("red", answer.answer.casefold())

    def test_memory_intent_recall_bundles_top_sessions_before_verbose_seeds(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            store = ConversationMemoryStore(Path(temp) / "memory.sqlite3", ROOT)
            store.ingest_session("u", "coupon-session", "coupon-session", (
                ConversationTurn("coupon-location", "user",
                    "The location was in the quiet riverside district near the station entrance.",
                    "2024-01-01T00:00:00+00:00"),
                ConversationTurn("coupon-filler", "assistant", "Shopping background. " * 200,
                    "2024-01-01T00:01:00+00:00"),
                ConversationTurn("coupon-seed", "user", "I redeemed the coupon there.",
                    "2024-01-01T00:02:00+00:00")))
            for index in range(6):
                store.ingest_session("u", f"coupon-distractor-{index}",
                    f"coupon-distractor-{index}", (ConversationTurn(f"coupon-noise-{index}",
                    "assistant", "Generic " + "coupon guidance " * 99,
                    f"2024-02-{index + 1:02d}T00:00:00+00:00"),))
            coupon = store.retrieve("u", "Where could I redeem that coupon?", limit=8,
                                    max_prompt_chars=8000)
            self.assertEqual("coupon-session", coupon[0].session_id)
            location_index = next(index for index, item in enumerate(coupon)
                                  if item.turn_id == "coupon-location")
            first_noise = next(index for index, item in enumerate(coupon)
                               if item.session_id.startswith("coupon-distractor"))
            self.assertEqual(first_noise + 1, location_index)
            self.assertTrue(any(item.session_id.startswith("coupon-distractor")
                                for item in coupon[location_index + 1:]))
            self.assertLess(sum(len(item.content) for item in coupon), 8001)

            store.ingest_session("u", "preferences", "preferences", (
                ConversationTurn("preference", "user",
                    "I prefer quiet indoor options and avoid crowds.",
                    "2024-03-01T00:00:00+00:00"),
                ConversationTurn("preference-response", "assistant",
                    "A calm reading circle would fit those constraints.",
                    "2024-03-01T00:01:00+00:00"),
                ConversationTurn("preference-time", "user",
                    "I only have time after work and want a short scope.",
                    "2024-03-01T00:02:00+00:00")))
            for index in range(6):
                store.ingest_session("u", f"activity-{index}", f"activity-{index}", (
                    ConversationTurn(f"activity-{index}", "assistant",
                        "Evening activities can include generic entertainment and social events.",
                        f"2024-04-{index + 1:02d}T00:00:00+00:00"),))
            recommendations = store.retrieve(
                "u", "Could you suggest activities for the evening?", limit=8)
            preference_hits = tuple(item for item in recommendations
                                    if item.session_id == "preferences")
            self.assertEqual({"preference", "preference-response", "preference-time"},
                             {item.turn_id for item in preference_hits})
            self.assertLess(max(recommendations.index(item) for item in preference_hits), 5)

            store.ingest_session("u", "instrument", "instrument", (
                ConversationTurn("instrument-compare", "user",
                    "I compared my entry instrument with an upgraded solid-top model.",
                    "2024-05-01T00:00:00+00:00"),
                ConversationTurn("instrument-response", "assistant",
                    "The upgrade would improve resonance for your practice goals.",
                    "2024-05-01T00:01:00+00:00"),
                ConversationTurn("instrument-latest", "user",
                    "I am excited about the instrument now.",
                    "2024-05-01T00:02:00+00:00")))
            for index in range(6):
                store.ingest_session("u", f"music-{index}", f"music-{index}", (
                    ConversationTurn(f"music-{index}", "assistant",
                        "I am excited for new music equipment and can offer general looking tips.",
                        f"2024-06-{index + 1:02d}T00:00:00+00:00"),))
            item_hits = store.retrieve(
                "u", "I am excited for a new instrument and music equipment; what should I look for?",
                limit=8)
            self.assertEqual("instrument", item_hits[0].session_id)
            self.assertTrue({"instrument-compare", "instrument-response", "instrument-latest"}
                            .issubset({item.turn_id for item in item_hits[:5]}))

            education = (
                ("certificate", "My certificate program lasted 2 years."),
                ("diploma", "The diploma stage took 18 months."),
                ("degree", "The undergraduate degree required 4 years."),
            )
            for index, (session_id, content) in enumerate(education):
                store.ingest_session("u", session_id, session_id, (ConversationTurn(
                    session_id, "user", content, f"2024-07-{index + 1:02d}T00:00:00+00:00"),))
            quantitative = store.retrieve(
                "u", "How long was my education in total, including the final stage?", limit=8)
            known = {item.turn_id for item in quantitative}
            self.assertTrue({"certificate", "diploma", "degree"}.issubset(known))

        known_ids = [item.memory_id for item in quantitative
                     if item.turn_id in {"certificate", "diploma", "degree"}]
        partial = {"answer": "Known stages have durations, while the final stage is missing.",
                   "supporting_memory_ids": known_ids, "abstain": True}
        client, runner = self.client([json.dumps(partial)])
        answer = CodexMemoryAnswerer(client).answer(
            "How long was my education in total, including the final stage?", quantitative)
        self.assertTrue(answer.abstain)
        self.assertEqual(tuple(known_ids), answer.supporting_memory_ids)
        self.assertEqual(1, len(runner.calls))

    def test_memory_direct_companions_education_constraints_and_product_history(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            store = ConversationMemoryStore(Path(temp) / "memory.sqlite3", ROOT)
            store.ingest_session("u", "workshop", "workshop", (
                ConversationTurn("workshop-duration", "user", "It lasted six weeks.",
                                 "2024-01-01T00:00:00+00:00"),
                ConversationTurn("workshop-context", "user", "The room was quiet.",
                                 "2024-01-01T00:01:00+00:00"),
                ConversationTurn("workshop-seed", "user", "The advanced workshop was memorable.",
                                 "2024-01-01T00:02:00+00:00")))
            workshop = store.retrieve("u", "How long was the advanced workshop?", limit=2)
            self.assertEqual(["workshop-seed", "workshop-duration"],
                             [item.turn_id for item in workshop])
            self.assertEqual("conversation_turn", workshop[1].provenance)

            stages = (
                ("school-stage", "High-school took four years."),
                ("associate-stage", "My associate degree lasted two years."),
                ("undergraduate-stage", "Undergraduate college study lasted three years."),
            )
            for index, (session_id, content) in enumerate(stages):
                store.ingest_session("u", session_id, session_id, (ConversationTurn(
                    session_id, "user", content, f"2024-02-{index + 1:02d}T00:00:00+00:00"),))
            education = store.retrieve("u",
                "Which education stages did I complete, including their lengths and any missing final stage?",
                limit=8)
            stage_ids = {item.turn_id for item in education}
            self.assertTrue({item[0] for item in stages}.issubset(stage_ids))

            store.ingest_session("u", "constraints", "constraints", (
                ConversationTurn("constraint-user", "user",
                    "I prefer low-noise spaces in the early evening.",
                    "2024-03-01T00:00:00+00:00"),
                ConversationTurn("constraint-screen", "assistant",
                    "Avoid crowded venues when screening the options.",
                    "2024-03-01T00:01:00+00:00")))
            for index in range(7):
                store.ingest_session("u", f"domain-{index}", f"domain-{index}", (
                    ConversationTurn(f"domain-{index}", "assistant",
                        "Creative outdoor activity ideas include popular social entertainment.",
                        f"2024-04-{index + 1:02d}T00:00:00+00:00"),))
            recommendation = store.retrieve(
                "u", "Suggest creative outdoor activity ideas for me.", limit=8)
            self.assertIn("constraints", {item.session_id for item in recommendation[:2]})
            self.assertTrue({"constraint-user", "constraint-screen"}.issubset(
                {item.turn_id for item in recommendation[:5]}))

            store.ingest_session("u", "product", "product", (
                ConversationTurn("product-compare", "user",
                    "I compared the upgraded guitar with the standard guitar and noted differences.",
                    "2024-05-01T00:00:00+00:00"),
                ConversationTurn("product-context", "assistant", "Product background. " * 200,
                    "2024-05-01T00:01:00+00:00"),
                ConversationTurn("product-use", "user",
                    "I have been using the guitars during daily practice.",
                    "2024-05-01T00:02:00+00:00")))
            product = store.retrieve(
                "u", "What was different about the guitar, and how did I use it?", limit=4)
            product_hits = {item.turn_id: item for item in product}
            self.assertTrue({"product-compare", "product-use"}.issubset(product_hits))
            self.assertTrue({"compare", "guitar"}.issubset(
                product_hits["product-compare"].matched_terms))
            self.assertEqual(("guitar", "use"), product_hits["product-use"].matched_terms)

        known_ids = [item.memory_id for item in education if item.turn_id in {item[0] for item in stages}]
        partial = {"answer": "The three known stages have durations; a later stage is missing.",
                   "supporting_memory_ids": known_ids, "abstain": True}
        client, runner = self.client([json.dumps(partial)])
        answer = CodexMemoryAnswerer(client).answer(
            "Which education stages did I complete, including their lengths?", education)
        self.assertTrue(answer.abstain)
        self.assertEqual(tuple(known_ids), answer.supporting_memory_ids)
        self.assertIn("four years", runner.calls[0][1])
        self.assertIn("two years", runner.calls[0][1])
        self.assertIn("three years", runner.calls[0][1])

    def test_memory_stage_timelines_and_evidence_bound_comparison_checklist(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            store = ConversationMemoryStore(Path(temp) / "memory.sqlite3", ROOT)
            stages = (
                ("foundation", "Foundation training ran from 2011 to 2014."),
                ("intermediate", "Intermediate certification covered 2015-2017, a three-year stage."),
                ("advanced", "Advanced study lasted two years, from 2018 through 2019."),
                ("final", "Final specialization began later; its end date and duration were never recorded."),
            )
            for index, (turn_id, content) in enumerate(stages):
                store.ingest_session("u", turn_id, turn_id, (ConversationTurn(
                    turn_id, "user", content, f"2024-01-{index + 1:02d}T00:00:00+00:00"),))
            for index in range(7):
                store.ingest_session("u", f"stage-noise-{index}", f"stage-noise-{index}", (
                    ConversationTurn(f"stage-noise-{index}", "assistant",
                        "General training completion advice discusses schedules, planning, and "
                        "professional development without a personal timeline. " * 8,
                        f"2024-02-{index + 1:02d}T00:00:00+00:00"),))
            timeline = store.retrieve(
                "u", "Summarize my training stage timeline and identify the missing duration.",
                limit=8, max_prompt_chars=8000)
            stage_hits = {item.turn_id: item for item in timeline if item.role == "user"}
            self.assertTrue({item[0] for item in stages}.issubset(stage_hits))
            self.assertLess(max(timeline.index(stage_hits[item[0]]) for item in stages), 8)

            store.ingest_session("u", "device-history", "device-history", (
                ConversationTurn("device-comparison", "user",
                    "My current device is compact; the target upgrade should be lighter with better "
                    "battery performance.", "2024-03-01T00:00:00+00:00"),
                ConversationTurn("device-background", "assistant",
                    "Generic purchasing background. " * 180,
                    "2024-03-01T00:01:00+00:00"),
                ConversationTurn("device-usage", "user",
                    "I use it daily for field work, prefer a firm grip, and avoid sharp edges.",
                    "2024-03-01T00:02:00+00:00")))
            for index in range(7):
                store.ingest_session("u", f"device-noise-{index}", f"device-noise-{index}", (
                    ConversationTurn(f"device-noise-{index}", "assistant",
                        "General equipment recommendations cover shopping options and popular advice. "
                        * 8, f"2024-04-{index + 1:02d}T00:00:00+00:00"),))
            comparison = store.retrieve(
                "u", "Recommend what I should evaluate before replacing my equipment.",
                limit=8, max_prompt_chars=8000)
            comparison_ids = {item.turn_id for item in comparison}
            self.assertTrue({"device-comparison", "device-usage"}.issubset(comparison_ids))

        timeline_ids = [stage_hits[item[0]].memory_id for item in stages]
        comparison_support = [item.memory_id for item in comparison
                              if item.turn_id in {"device-comparison", "device-usage"}]
        outputs = (
            {"answer": "Known ranges are 2011-2014, 2015-2017, and 2018-2019; "
                       "the final specialization duration is missing.",
             "supporting_memory_ids": timeline_ids, "abstain": True},
            {"answer": "Compare the compact current device with the lighter target on battery, "
                       "daily field use, grip, and edge comfort; price remains an evidence gap.",
             "supporting_memory_ids": comparison_support, "abstain": False},
        )
        client, runner = self.client([json.dumps(item) for item in outputs])
        partial = CodexMemoryAnswerer(client).answer(
            "Summarize my training stage timeline and identify the missing duration.", timeline)
        guidance = CodexMemoryAnswerer(client).answer(
            "Recommend what I should evaluate before replacing my equipment.", comparison)
        self.assertTrue(partial.abstain)
        self.assertEqual(tuple(timeline_ids), partial.supporting_memory_ids)
        self.assertFalse(guidance.abstain)
        timeline_prompt = runner.calls[0][1]
        self.assertIn("2011 to 2014", timeline_prompt)
        self.assertIn("2015-2017", timeline_prompt)
        self.assertIn("2018 through 2019", timeline_prompt)
        self.assertIn("duration were never recorded", timeline_prompt)
        comparison_prompt = runner.calls[1][1]
        self.assertIn("current device is compact", comparison_prompt)
        self.assertIn("daily for field work", comparison_prompt)
        self.assertIn("current item or context", comparison_prompt)
        self.assertIn("unsupported dimensions as evidence gaps", comparison_prompt)
        self.assertIn("generic shopping advice", comparison_prompt)
        self.assertEqual(tuple(comparison_support), guidance.supporting_memory_ids)

    def test_memory_comparison_expansion_requires_explicit_change_intent(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            store = ConversationMemoryStore(Path(temp) / "memory.sqlite3", ROOT)
            store.ingest_session("u", "activity-preference", "activity-preference", (
                ConversationTurn("activity-preference", "user",
                    "I prefer a quiet setting and avoid crowds.",
                    "2024-01-01T00:00:00+00:00"),
                ConversationTurn("activity-time", "user",
                    "I have time in the evening for a short activity.",
                    "2024-01-01T00:01:00+00:00")))
            for index in range(7):
                store.ingest_session("u", f"comparison-noise-{index}",
                    f"comparison-noise-{index}", (ConversationTurn(
                        f"comparison-noise-{index}", "user",
                        "My current equipment target uses daily performance tracking.",
                        f"2024-02-{index + 1:02d}T00:00:00+00:00"),))
            store.ingest_session("u", "legacy-compare-noise", "legacy-compare-noise", (
                ConversationTurn("legacy-compare-noise", "user",
                    "I compared and upgraded unrelated equipment.",
                    "2024-02-08T00:00:00+00:00"),))
            recommendation = store.retrieve(
                "u", "Suggest a short activity for my evening.", limit=8,
                max_prompt_chars=8000)
            self.assertEqual({"activity-preference"},
                             {item.session_id for item in recommendation})
            self.assertEqual({"activity-preference", "activity-time"},
                             {item.turn_id for item in recommendation})

            store.ingest_session("u", "explicit-comparison", "explicit-comparison", (
                ConversationTurn("explicit-current-target", "user",
                    "My current device is compact and the target replacement should be lighter.",
                    "2024-03-01T00:00:00+00:00"),
                ConversationTurn("explicit-usage", "user",
                    "I use it daily and need stronger battery performance.",
                    "2024-03-01T00:01:00+00:00")))
            comparison = store.retrieve(
                "u", "Compare my current compact device with the lighter target upgrade for daily use.",
                limit=8,
                max_prompt_chars=8000)
            self.assertTrue({"explicit-current-target", "explicit-usage"}.issubset(
                {item.turn_id for item in comparison}))

    def test_memory_answer_guides_qualified_session_linkage_and_conflict_abstention(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            store = ConversationMemoryStore(Path(temp) / "memory.sqlite3", ROOT)
            store.ingest_session("u", "clear-link", "clear-link", (
                ConversationTurn("clear-entity", "user",
                    "The shop I chose was in the riverside district.",
                    "2024-06-01T00:00:00+00:00"),
                ConversationTurn("clear-event", "user", "I later redeemed the coupon there.",
                    "2024-06-01T00:01:00+00:00")))
            clear_hits = store.retrieve("u", "Where did I redeem the coupon?", limit=4)
            store.ingest_session("u", "ambiguous-link", "ambiguous-link", (
                ConversationTurn("first-entity", "user",
                    "One shop was in the northern district.",
                    "2024-07-01T00:00:00+00:00"),
                ConversationTurn("second-entity", "user",
                    "Another shop was in the southern district.",
                    "2024-07-01T00:01:00+00:00"),
                ConversationTurn("ambiguous-event", "user", "I redeemed the coupon there.",
                    "2024-07-01T00:02:00+00:00")))
            ambiguous_hits = store.retrieve("u", "Where did I redeem the coupon?", limit=4)
        clear_ids = [item.memory_id for item in clear_hits
                     if item.turn_id in {"clear-entity", "clear-event"}]
        ambiguous_ids = [item.memory_id for item in ambiguous_hits
                         if item.turn_id in {"first-entity", "second-entity", "ambiguous-event"}]
        outputs = (
            {"answer": "It likely refers to the riverside district from the same session.",
             "supporting_memory_ids": clear_ids, "abstain": False},
            {"answer": "Two locations conflict, so the coupon location is ambiguous.",
             "supporting_memory_ids": ambiguous_ids, "abstain": True},
        )
        client, runner = self.client([json.dumps(item) for item in outputs])
        linked = CodexMemoryAnswerer(client).answer("Where did I redeem the coupon?", clear_hits)
        ambiguous = CodexMemoryAnswerer(client).answer(
            "Where did I redeem the coupon?", ambiguous_hits)
        self.assertFalse(linked.abstain)
        self.assertTrue(ambiguous.abstain)
        self.assertEqual(tuple(clear_ids), linked.supporting_memory_ids)
        self.assertEqual(tuple(ambiguous_ids), ambiguous.supporting_memory_ids)
        self.assertIn("qualified inference", runner.calls[0][1])
        self.assertIn("conflicting entities", runner.calls[0][1])
        self.assertEqual(2, len(runner.calls))

    def test_memory_prompt_supports_aggregation_temporal_order_and_same_session_join(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            store = ConversationMemoryStore(Path(temp) / "memory.sqlite3", ROOT)
            store.ingest_session("u", "break-a", "break-a", (ConversationTurn("a", "user",
                "The first break lasted 7 days.", "2024-01-01T00:00:00+00:00"),))
            store.ingest_session("u", "break-b", "break-b", (ConversationTurn("b", "user",
                "The second break lasted 10 day.", "2024-02-01T00:00:00+00:00"),))
            duration_hits = store.retrieve("u", "How many days did both breaks last?", limit=4)
            store.ingest_session("u", "shop", "shop", (
                ConversationTurn("location", "user", "It was located in Kyoto.",
                                 "2024-03-01T00:00:00+00:00"),
                ConversationTurn("coupon", "user", "I saved a coupon for that store.",
                                 "2024-03-01T00:01:00+00:00")))
            join_hits = store.retrieve("u", "Where was the store with my coupon?", limit=4)
            store.ingest_session("u", "events-a", "events-a", (ConversationTurn("early", "user",
                "The conference event occurred.", "2023-05-01T00:00:00+00:00"),))
            store.ingest_session("u", "events-b", "events-b", (ConversationTurn("late", "user",
                "The workshop event occurred.", "2024-05-01T00:00:00+00:00"),))
            temporal_hits = store.retrieve("u", "Which event occurred earlier?", limit=4)
        duration_ids = [item.memory_id for item in duration_hits if item.turn_id in {"a", "b"}]
        output = {"answer": "The two breaks totaled 17 days.",
                  "supporting_memory_ids": duration_ids, "abstain": False}
        client, runner = self.client([json.dumps(output)])
        answer = CodexMemoryAnswerer(client, max_prompt_chars=1000).answer(
            "How many days did both breaks last?", duration_hits)
        self.assertIn("17 days", answer.answer)
        prompt = runner.calls[0][1]
        self.assertIn("sum explicit durations or counts", prompt)
        self.assertIn("7 days", prompt)
        self.assertIn("10 day", prompt)
        self.assertLessEqual(sum(len(item.content) for item in duration_hits),
                             1000 - len("How many days did both breaks last?"))
        self.assertEqual(("coupon", "location"), (join_hits[0].turn_id, join_hits[-1].turn_id))
        self.assertEqual("same_session_context", join_hits[-1].provenance)
        self.assertEqual({"early", "late"}, {item.turn_id for item in temporal_hits[:2]})
        dates = {item.turn_id: item.occurred_at for item in temporal_hits}
        self.assertLess(dates["early"], dates["late"])
        self.assertIn("compare occurred_at timestamps", prompt)
        temporal_ids = [item.memory_id for item in temporal_hits if item.turn_id in {"early", "late"}]
        join_ids = [item.memory_id for item in join_hits if item.turn_id in {"coupon", "location"}]
        temporal_output = {"answer": "The conference event occurred first.",
                           "supporting_memory_ids": temporal_ids, "abstain": False}
        join_output = {"answer": "The coupon's store was in Kyoto.",
                       "supporting_memory_ids": join_ids, "abstain": False}
        role_client, role_runner = self.client([json.dumps(temporal_output), json.dumps(join_output)])
        temporal = CodexMemoryAnswerer(role_client).answer("Which event occurred earlier?", temporal_hits)
        joined = CodexMemoryAnswerer(role_client).answer("Where was the store with my coupon?", join_hits)
        self.assertIn("conference", temporal.answer)
        self.assertIn("Kyoto", joined.answer)
        self.assertIn("same_session_context", role_runner.calls[1][1])
        self.assertEqual(2, len(role_runner.calls))

    def test_failed_memory_repair_returns_safe_abstention_with_hits_and_typed_error(self):
        fabricated = {"answer": "fabricated", "supporting_memory_ids": ["memory:s1:fake"],
                      "abstain": False}
        client, runner = self.client([json.dumps(fabricated), json.dumps(fabricated)])
        class NeverPlanner:
            def plan(self, *args, **kwargs): raise AssertionError("planner must not run")
        class NeverController:
            def run(self, *args, **kwargs): raise AssertionError("controller must not run")
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            path = Path(temp) / "memory.sqlite3"
            memory_store = ConversationMemoryStore(path, ROOT)
            memory_store.ingest_session("u", "old", "s1", (ConversationTurn("t1", "user",
                "The interval was 17 days.", "2024-01-01T00:00:00+00:00"),))
            service = ResearchService(NeverPlanner(), NeverController(),
                SQLiteResearchStore(path, ROOT), ROOT, memory_store=memory_store,
                memory_answerer=CodexMemoryAnswerer(client), clock=lambda: date(2024, 12, 31))
            result = service.ask_memory("u", "fresh", "What was the interval?", persist=False)
            self.assertEqual((True, ()), (result.abstain, result.supporting_memory_ids))
            self.assertEqual(("memory:s1:t1",), tuple(item.memory_id for item in result.hits))
            self.assertIsNotNone(result.recovery_error)
            runner.outputs.extend((json.dumps(fabricated), json.dumps(fabricated)))
            frames = tuple(service.stream_payload("u", {"message": "What was the interval?",
                           "chat_id": "fresh", "files": [], "mode": "memory"}))
        self.assertIn("cannot answer reliably", "".join(frames))
        self.assertNotIn("memory:s1:fake", "".join(frames))
        events = service.typed_events[("u", "fresh")]
        self.assertEqual(("message.delta", "error", "done"), tuple(item.kind for item in events))
        self.assertEqual(("memory_answer", True),
                         (events[1].payload["stage"], events[1].payload["recoverable"]))
        self.assertEqual(4, len(runner.calls))

    def test_research_service_memory_mode_recall_has_zero_research_calls_and_persists_turns(self):
        class NeverPlanner:
            calls = 0
            def plan(self, *args, **kwargs):
                self.calls += 1
                raise AssertionError("planner must not run in memory mode")
        class NeverController:
            calls = 0
            def run(self, *args, **kwargs):
                self.calls += 1
                raise AssertionError("controller must not run in memory mode")
        response = {"answer": "You prefer morning meetings.",
                    "supporting_memory_ids": ["memory:old-session:pref"], "abstain": False}
        client, runner = self.client([json.dumps(response), json.dumps(response)])
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            path = Path(temp) / "memory.sqlite3"
            research_store = SQLiteResearchStore(path, ROOT)
            memory_store = ConversationMemoryStore(path, ROOT)
            memory_store.ingest_session("alice", "old-chat", "old-session", (
                ConversationTurn("pref", "user", "I prefer morning meetings.",
                                 "2024-03-01T10:00:00+00:00"),))
            planner, controller = NeverPlanner(), NeverController()
            service = ResearchService(planner, controller, research_store, ROOT,
                memory_store=memory_store, memory_answerer=CodexMemoryAnswerer(client),
                clock=lambda: date(2024, 12, 31))
            frames = tuple(service.stream_payload("alice", {"message": "What is my preference?",
                           "chat_id": "fresh-chat", "files": [], "mode": "memory"}))
            self.assertIn("morning meetings", "".join(frames))
            self.assertEqual((0, 0), (planner.calls, controller.calls))
            self.assertEqual("memory", service.typed_events[("alice", "fresh-chat")][0].agent)
            self.assertNotIn('"session_id": "fresh-chat"', runner.calls[0][1])
            self.assertEqual(3, memory_store.count("alice"))
            auto = tuple(service.stream_payload("alice", {"message": "Do you remember my preference?",
                         "chat_id": "another-chat", "files": []}))
            self.assertIn("morning meetings", "".join(auto))
            self.assertEqual((0, 0), (planner.calls, controller.calls))
            self.assertEqual(5, ConversationMemoryStore(path, ROOT).count("alice"))
            self.assertTrue(all("What is my preference?" not in item.content
                                for item in memory_store.retrieve("alice", "morning meetings", limit=2)))
            self.assertEqual(2, len(runner.calls))

    def test_shifted_app_history_uses_content_stable_turn_identity(self):
        class Planner:
            def plan(self, question, as_of, context, history=()):
                plan = SearchPlan("p-" + question, question, as_of, ("Q",), ("europe_pmc",),
                                  ("relevant",), ("unrelated",), ("complete",))
                return ResearchRequest(plan, (ResearchQuery("europe-pmc.search", "europe_pmc", "Q"),))
        class Controller:
            def run(self, request, context, checkpoint=None, revoked_record_ids=()):
                saved = WorkflowCheckpoint((request.plan.id,), ())
                return type("Result", (), {"answer": "saved answer", "checkpoint": saved,
                    "ledger": type("Ledger", (), {"admitted": lambda self: ()})(), "events": ()})()
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            path = Path(temp) / "memory.sqlite3"
            memory_store = ConversationMemoryStore(path, ROOT)
            service = ResearchService(Planner(), Controller(), SQLiteResearchStore(path, ROOT), ROOT,
                memory_store=memory_store, memory_answerer=object(),
                clock=lambda: date(2024, 12, 31))
            first = ({"content": "alphaunique fact", "role": "user"},
                     {"content": "betaunique fact", "role": "assistant"})
            shifted = ({"content": "betaunique fact", "role": "assistant"},
                       {"content": "gammaunique fact", "role": "user"})
            tuple(service.stream_payload("u", {"message": "research one", "chat_id": "rolling",
                  "files": [], "mode": "research"}, history=first))
            tuple(service.stream_payload("u", {"message": "research two", "chat_id": "rolling",
                  "files": [], "mode": "research"}, history=shifted))
            for term in ("alphaunique", "betaunique", "gammaunique"):
                hits = memory_store.retrieve("u", term, limit=8)
                direct = tuple(hit for hit in hits if hit.provenance == "conversation_turn")
                self.assertEqual(1, len(direct))
                self.assertIn(term, direct[0].content)
                self.assertEqual(len(hits), len({hit.memory_id for hit in hits}))
            self.assertEqual(7, memory_store.count("u"))


if __name__ == "__main__":
    unittest.main()
