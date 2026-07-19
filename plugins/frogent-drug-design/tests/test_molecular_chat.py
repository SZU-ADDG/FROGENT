"""Behavior tests for exact-identity ADMET chat and app-v4 integration."""

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from frogent_plugin.admet_execution import (  # noqa: E402
    ADMETBatchPrediction, DEFAULT_ADMET_PROPERTIES,
)
from frogent_plugin.app_v4_bridge import AppV4ResearchManager  # noqa: E402
from frogent_plugin.codex_client import CodexClient  # noqa: E402
from frogent_plugin.conversation_memory import ConversationMemoryStore  # noqa: E402
from frogent_plugin.contracts import ExecutionContext  # noqa: E402
from frogent_plugin.molecular_chat import MolecularChatHandler, is_clear_admet_intent  # noqa: E402
from frogent_plugin.molecular_chat_plan import (  # noqa: E402
    CodexMolecularPlanner, MolecularChatEntity, MolecularChatPlan,
)
from frogent_plugin.molecular_identity import (  # noqa: E402
    DerivedMoleculeCandidate, MolecularIdentity,
)
from frogent_plugin.pubchem_identity import (  # noqa: E402
    PubChemExternalIdentity, PubChemResolution,
)
from frogent_plugin.research_memory import SQLiteResearchStore  # noqa: E402
from frogent_plugin.research_factory import RuntimeConfig, build_research_service  # noqa: E402
from frogent_plugin.research_service import ResearchService  # noqa: E402


CAFFEINE = "CN1C=NC2=C1C(=O)N(C(=O)N2C)C"
CAFFEINE_KEY = "RYYVLZVUVIJVGH-UHFFFAOYSA-N"
THEOBROMINE = "CN1C=NC2=C1C(=O)NC(=O)N2C"
THEOBROMINE_KEY = "YAPQBXQYLJRXSA-UHFFFAOYSA-N"


def identity(smiles, key, name="molecule", *, fragments=1, organic=1, parent=None):
    return MolecularIdentity(smiles, smiles, smiles, "InChI=1S/" + name, key, "C8H10N4O2",
        194.08, 0, 14, fragments, organic, "single" if fragments == 1 else
        ("salt_or_counterion" if organic == 1 else "multiple_organic_fragments"),
        fragments > 1, 0, 0, "none", parent)


class FakeRunner:
    def __init__(self, output):
        self.output, self.calls, self.schema = output, [], None

    def __call__(self, args, prompt, timeout, cwd):
        self.calls.append((args, prompt, timeout, cwd))
        path = Path(args[args.index("--output-schema") + 1])
        self.schema = json.loads(path.read_text())
        return self.output


class FakeNormalizer:
    def __init__(self, values):
        self.values = values

    def normalize(self, smiles):
        return self.values[smiles]


class FakeResolver:
    def __init__(self, values, *, name_error="", binding_error=""):
        self.normalizer = FakeNormalizer(values)
        self.values = values
        self.name_error, self.binding_error = name_error, binding_error
        self.calls = []

    def resolve_name(self, name):
        self.calls.append(("name", name))
        if self.name_error:
            return PubChemResolution(None, None, (), (self.name_error,))
        item = self.values[name]
        return _resolution(item, name, "resolved_name")

    def resolve_binding(self, binding):
        self.calls.append(("binding", binding.inchikey))
        if self.binding_error:
            return PubChemResolution(None, None, (), (self.binding_error,))
        item = next(value for value in self.values.values()
                    if value.inchikey == binding.inchikey)
        return _resolution(item, binding.canonical_isomeric_smiles, binding.scope)


class FakePredictor:
    provider_id = "fake-admet"
    model_name = "bounded-model"
    model_version = "test-1"

    def __init__(self, error=None):
        self.error, self.calls = error, []

    def predict(self, smiles):
        self.calls.append(smiles)
        if self.error:
            raise self.error
        rows = tuple({"AMES": 0.8 - index * 0.3, "DILI": 0.6 - index * 0.2}
                     for index in range(len(smiles)))
        return ADMETBatchPrediction(smiles, rows)


class StaticPlanner:
    def __init__(self, plan):
        self.value, self.calls = plan, []

    def plan(self, message):
        self.calls.append(message)
        return self.value


class FailingMemoryStore:
    def __init__(self, failure_stage):
        self.failure_stage, self.calls = failure_stage, []

    def ingest_session(self, user_id, conversation_id, session_id, turns):
        values = tuple(turns)
        self.calls.append(tuple(item.turn_id for item in values))
        stage = "history" if any(item.turn_id.startswith("history-") for item in values) \
            else "exchange" if any(item.turn_id.startswith("current-") for item in values) else ""
        if stage == self.failure_stage:
            raise RuntimeError(stage + " sqlite unavailable")
        return len(values)

    def turn_time(self, user_id, session_id, turn_id):
        return None


def _resolution(item, requested, scope):
    external = PubChemExternalIdentity(2519 if item.inchikey == CAFFEINE_KEY else 5429,
        "Caffeine" if item.inchikey == CAFFEINE_KEY else "Theobromine",
        item.canonical_connectivity_smiles, item.canonical_isomeric_smiles, item.inchi,
        item.inchikey, item.formula, item.formal_charge, "https://pubchem.example/compound",
        "verified_name", requested, scope)
    return PubChemResolution(external, item, (), ())


def _plan(operation="predict", *, kind="name", baseline=False, scope=None, selected=""):
    candidate = MolecularChatEntity(kind, "caffeine" if kind == "name" else CAFFEINE,
                                    scope, selected)
    other = MolecularChatEntity("name", "theobromine") if baseline else None
    return MolecularChatPlan(operation, candidate, other, ("AMES", "DILI"))


class MolecularChatTests(unittest.TestCase):
    def setUp(self):
        self.caffeine = identity(CAFFEINE, CAFFEINE_KEY, "caffeine")
        self.theobromine = identity(THEOBROMINE, THEOBROMINE_KEY, "theobromine")
        self.values = {"caffeine": self.caffeine, CAFFEINE: self.caffeine,
                       "theobromine": self.theobromine, THEOBROMINE: self.theobromine}
        self.context = ExecutionContext("u", "c", "j", ROOT)

    def test_native_planner_schema_and_exact_user_spans(self):
        output = {"operation": "compare", "candidate_kind": "name",
            "candidate_value": "caffeine", "baseline_kind": "name",
            "baseline_value": "theobromine", "candidate_scope": "unspecified",
            "candidate_structure_smiles": "", "candidate_selection_text": "",
            "baseline_scope": "unspecified", "baseline_structure_smiles": "",
            "baseline_selection_text": ""}
        runner = FakeRunner(json.dumps(output))
        planner = CodexMolecularPlanner(CodexClient(ROOT, runner=runner))
        plan = planner.plan("Compare ADMET of caffeine with theobromine")
        self.assertEqual(("candidate", "baseline"),
                         tuple(role for role, _ in (("candidate", plan.candidate),
                                                   ("baseline", plan.baseline))))
        self.assertFalse(runner.schema["additionalProperties"])
        self.assertNotIn("requested_properties", runner.schema["properties"])
        self.assertEqual(DEFAULT_ADMET_PROPERTIES, plan.requested_properties)
        self.assertIn("exact case-sensitive spans", runner.calls[0][1])
        explicit = CodexMolecularPlanner(CodexClient(ROOT, runner=FakeRunner(json.dumps(output))))
        explicit_plan = explicit.plan(
            "Compare AMES/hERG/DILI ADMET of caffeine with theobromine")
        self.assertEqual(("AMES", "hERG", "DILI"), explicit_plan.requested_properties)
        invented = {**output, "candidate_value": "aspirin"}
        bad = CodexMolecularPlanner(CodexClient(ROOT, runner=FakeRunner(json.dumps(invented))))
        with self.assertRaisesRegex(ValueError, "exact user-text span"):
            bad.plan("Compare ADMET of caffeine with theobromine")
        unused = {**output, "operation": "predict", "baseline_kind": "none",
                  "baseline_value": "", "baseline_scope": "full"}
        bad = CodexMolecularPlanner(CodexClient(ROOT, runner=FakeRunner(json.dumps(unused))))
        with self.assertRaisesRegex(ValueError, "unused baseline"):
            bad.plan("Run full ADMET for caffeine")
        arbitrary = {**output, "requested_properties": ["AMES"]}
        bad = CodexMolecularPlanner(CodexClient(ROOT, runner=FakeRunner(json.dumps(arbitrary))))
        with self.assertRaisesRegex(ValueError, "output fields"):
            bad.plan("Compare ADMET of caffeine with theobromine")

    def test_scope_selection_is_independently_bound_to_each_role(self):
        mixture = identity("CCO.CCN", "MIXTURE", fragments=2, organic=2)
        values = {**self.values, "CCO.CCN": mixture}
        base = {"operation": "compare", "candidate_kind": "name",
            "candidate_value": "caffeine", "baseline_kind": "smiles",
            "baseline_value": "CCO.CCN", "candidate_scope": "full",
            "candidate_structure_smiles": "", "candidate_selection_text": "full caffeine",
            "baseline_scope": "full", "baseline_structure_smiles": "",
            "baseline_selection_text": "full caffeine"}
        predictor = FakePredictor()
        invalid = MolecularChatHandler(CodexMolecularPlanner(CodexClient(
            ROOT, runner=FakeRunner(json.dumps(base)))), FakeResolver(values), predictor).run(
                "Compare full caffeine with CCO.CCN using AMES", self.context)
        self.assertIsNone(invalid.workflow)
        self.assertEqual([], predictor.calls)
        self.assertIn("baseline scope requires role-specific", invalid.answer)
        valid = {**base, "baseline_selection_text": "full CCO.CCN"}
        completed = MolecularChatHandler(CodexMolecularPlanner(CodexClient(
            ROOT, runner=FakeRunner(json.dumps(valid)))), FakeResolver(values), predictor).run(
                "Compare full caffeine with full CCO.CCN using AMES", self.context)
        self.assertEqual("completed", completed.workflow.execution.status)
        self.assertEqual(((CAFFEINE, "CCO.CCN"),), tuple(predictor.calls))
        self.assertEqual(("full", "full"), tuple(
            item.scope for item in completed.workflow.execution.input_bindings))

    def test_name_predict_and_comparison_render_exact_evidence(self):
        resolver, predictor = FakeResolver(self.values), FakePredictor()
        single = MolecularChatHandler(StaticPlanner(_plan()), resolver, predictor).run(
            "Run ADMET for caffeine", self.context)
        comparison = MolecularChatHandler(StaticPlanner(_plan("compare", baseline=True)),
                                          resolver, predictor).run(
            "Compare ADMET of caffeine with theobromine", self.context)
        self.assertEqual(((CAFFEINE,), (CAFFEINE, THEOBROMINE)), tuple(predictor.calls))
        self.assertIn(f"candidate: scope=full; SMILES={CAFFEINE}; InChIKey={CAFFEINE_KEY}",
                      single.answer)
        self.assertIn("candidate-minus-baseline.AMES=0.3", comparison.answer)
        self.assertIn("experimental_evidence=false", comparison.answer)
        payload = next(event.payload for event in comparison.events
                       if event.payload.get("capability_id") == "admet.compare"
                       and event.kind == "tool.completed")
        self.assertEqual(("candidate", "baseline"), tuple(payload["role_order"]))
        self.assertEqual((CAFFEINE_KEY, THEOBROMINE_KEY),
                         tuple(item["inchikey"] for item in payload["inputs"]))
        self.assertFalse(payload["experimental_evidence"])
        limitation = "model applicability domain and cross-endpoint score comparability are not established"
        self.assertIn(limitation, payload["warnings"])
        self.assertIn("Warning: " + limitation, comparison.answer)

    def test_blocked_selection_prevents_model_and_literature_identity_remains_available(self):
        parent = DerivedMoleculeCandidate("CCO", "CCO", "InChI=1S/ethanol", "ETHANOL",
                                          "C2H6O", ("CCN",))
        mixture = identity("CCO.CCN", "MIXTURE", fragments=2, organic=2, parent=parent)
        resolver = FakeResolver({"CCO.CCN": mixture})
        predictor = FakePredictor()
        plan = MolecularChatPlan("predict", MolecularChatEntity("smiles", "CCO.CCN"),
                                 None, ("AMES",))
        result = MolecularChatHandler(StaticPlanner(plan), resolver, predictor).run(
            "Run ADMET for CCO.CCN", self.context)
        self.assertEqual([], predictor.calls)
        self.assertEqual("blocked", result.workflow.execution.status)
        self.assertEqual("MIXTURE", result.workflow.intake.search_terms[1].value)
        self.assertTrue(any(event.kind == "error" for event in result.events))

    def test_pubchem_gap_continues_local_prediction_and_model_failure_is_safe(self):
        resolver = FakeResolver(self.values, binding_error="PubChem offline")
        plan = _plan(kind="smiles")
        completed = MolecularChatHandler(StaticPlanner(plan), resolver, FakePredictor()).run(
            "Run ADMET for " + CAFFEINE, self.context)
        failed_predictor = FakePredictor(RuntimeError("model unavailable"))
        failed = MolecularChatHandler(StaticPlanner(plan), resolver, failed_predictor).run(
            "Run ADMET for " + CAFFEINE, self.context)
        self.assertEqual("completed", completed.workflow.execution.status)
        self.assertIn("PubChem offline", completed.answer)
        self.assertEqual("failed", failed.workflow.execution.status)
        self.assertIn(CAFFEINE_KEY, failed.answer)
        self.assertIn("model unavailable", failed.answer)
        self.assertTrue(any(event.kind == "error" for event in failed.events))

    def test_service_app_bridge_sse_events_and_memory_persistence(self):
        predictor = FakePredictor()
        handler = MolecularChatHandler(StaticPlanner(_plan()), FakeResolver(self.values), predictor)
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / "memory.sqlite"
            memory = ConversationMemoryStore(path, ROOT)
            service = ResearchService(_NeverPlanner(), _NeverController(),
                SQLiteResearchStore(path, ROOT), ROOT, memory_store=memory,
                molecular_handler=handler, clock=lambda: date(2026, 7, 19))
            manager = AppV4ResearchManager(service, lambda user: "chat-7")
            frames = tuple(manager.chat_stream("user-3", "Run ADMET for caffeine", []))
            self.assertIn('"name": "molecular"', frames[0])
            self.assertIn('"stop": true', frames[1])
            self.assertEqual("data: [DONE]\n\n", frames[2])
            events = service.typed_events[("user-3", "chat-7")]
            self.assertEqual(("tool.started", "tool.completed"),
                             (events[0].kind, events[1].kind))
            self.assertEqual(("molecular.plan", "molecular.plan", "pubchem.identity",
                              "pubchem.identity", "admet.predict", "admet.predict"),
                tuple(event.payload.get("capability_id") for event in events[:6]))
            self.assertEqual("done", events[-1].kind)
            self.assertEqual(2, memory.count("user-3"))
            self.assertEqual(1, len(predictor.calls))

    def test_explicit_mode_failure_is_persisted_and_auto_routing_is_conservative(self):
        predictor = FakePredictor(RuntimeError("model unavailable"))
        handler = MolecularChatHandler(StaticPlanner(_plan()), FakeResolver(self.values), predictor)
        self.assertTrue(is_clear_admet_intent("Run ADMET for caffeine"))
        self.assertFalse(is_clear_admet_intent("Find literature about caffeine ADMET"))
        self.assertFalse(is_clear_admet_intent("Compare papers about caffeine ADMET"))
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / "memory.sqlite"
            memory = ConversationMemoryStore(path, ROOT)
            planner = _NeverPlanner()
            service = ResearchService(planner, _NeverController(), SQLiteResearchStore(path, ROOT),
                ROOT, memory_store=memory, molecular_handler=handler)
            frames = tuple(service.stream_payload("u", {"message": "Run ADMET for caffeine",
                "chat_id": "failed", "files": [], "mode": "molecular"}))
            self.assertIn("model unavailable", frames[0])
            self.assertEqual(2, memory.count("u"))
            ordinary = tuple(service.stream_payload("u", {"message":
                "Find literature about caffeine ADMET", "chat_id": "research", "files": []}))
            self.assertIn("research planner called", ordinary[0])
            self.assertEqual(1, planner.calls)
            self.assertEqual(1, len(predictor.calls))

    def test_chinese_admet_actions_route_and_research_markers_remain_research(self):
        actions = ("请运行咖啡因的 ADMET", "请执行咖啡因 ADMET", "请预测咖啡因的ADMET",
                   "请计算咖啡因 ADMET", "请估算咖啡因 ADMET",
                   "请比较咖啡因与茶碱的 ADMET", "请评估咖啡因 ADMET")
        research = ("请搜索咖啡因 ADMET 文献", "请比较 ADMET 相关论文",
                    "请检索 ADMET 出版物", "请查找 ADMET publication")
        self.assertTrue(all(is_clear_admet_intent(value) for value in actions))
        self.assertFalse(any(is_clear_admet_intent(value) for value in research))
        self.assertFalse(is_clear_admet_intent("咖啡因的 ADMET 信息"))
        predictor = FakePredictor()
        handler = MolecularChatHandler(StaticPlanner(_plan()), FakeResolver(self.values), predictor)
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / "memory.sqlite"
            planner = _NeverPlanner()
            service = ResearchService(planner, _NeverController(), SQLiteResearchStore(path, ROOT),
                ROOT, molecular_handler=handler)
            molecular = tuple(service.stream_payload("u", {"message": actions[2],
                "chat_id": "zh-admet", "files": []}))
            literature = tuple(service.stream_payload("u", {"message": research[0],
                "chat_id": "zh-literature", "files": []}))
        self.assertIn('"name": "molecular"', molecular[0])
        self.assertIn("research planner called", literature[0])
        self.assertEqual((1, 1), (len(predictor.calls), planner.calls))

    def test_molecular_answer_survives_history_and_exchange_memory_failures(self):
        for stage in ("history", "exchange"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory(dir=ROOT) as directory:
                predictor = FakePredictor()
                handler = MolecularChatHandler(StaticPlanner(_plan()),
                    FakeResolver(self.values), predictor)
                path = Path(directory) / "research.sqlite"
                service = ResearchService(_NeverPlanner(), _NeverController(),
                    SQLiteResearchStore(path, ROOT), ROOT,
                    memory_store=FailingMemoryStore(stage), molecular_handler=handler)
                history = ([{"role": "assistant", "content": "prior molecular context"}]
                           if stage == "history" else [])
                frames = tuple(service.stream_payload("u", {"message":
                    "Run ADMET for caffeine", "chat_id": "memory-failure", "files": []},
                    history=history))
                self.assertIn('"name": "molecular"', frames[0])
                self.assertIn("conversation memory persistence failed", frames[0])
                self.assertIn('"stop": true', frames[1])
                self.assertEqual("data: [DONE]\n\n", frames[2])
                events = service.typed_events[("u", "memory-failure")]
                errors = tuple(item for item in events if item.kind == "error"
                               and item.payload.get("stage") == "memory_persistence")
                self.assertEqual(1, len(errors))
                self.assertTrue(errors[0].payload["recoverable"])
                self.assertEqual("done", events[-1].kind)
                self.assertEqual(1, len(predictor.calls))

    def test_factory_composes_lazy_reusable_admet_path(self):
        planner_output = {"operation": "predict", "candidate_kind": "name",
            "candidate_value": "caffeine", "baseline_kind": "none", "baseline_value": "",
            "candidate_scope": "unspecified", "candidate_structure_smiles": "",
            "candidate_selection_text": "", "baseline_scope": "unspecified",
            "baseline_structure_smiles": "", "baseline_selection_text": ""}
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            runner = FakeRunner(json.dumps(planner_output))
            service = build_research_service(RuntimeConfig(root, root / "memory.sqlite"),
                                             runner=runner, pdf_extractor=object())
            self.assertIsNotNone(service.molecular_handler)
            predictor = service.molecular_handler.predictor
            self.assertIsNone(predictor._model)
            self.assertEqual(root / ".runtime" / "app-v4" / "matplotlib",
                             predictor._matplotlib_cache)


class _NeverPlanner:
    def __init__(self):
        self.calls = 0

    def plan(self, *args, **kwargs):
        self.calls += 1
        raise RuntimeError("research planner called")


class _NeverController:
    def run(self, *args, **kwargs):
        raise AssertionError("research controller must not run")


if __name__ == "__main__":
    unittest.main()
