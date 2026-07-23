"""Behavior tests for the direct qualitative-design Agent path."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from frogent_plugin.contracts import ExecutionContext  # noqa: E402
from frogent_plugin.decision_policy import (  # noqa: E402
    CalibrationFinding, CalibrationOutcome,
)
from frogent_plugin.design_memory import SQLiteDesignStore  # noqa: E402
from frogent_plugin.design_workflow import QualitativeDesignHandler  # noqa: E402
from frogent_plugin.qualitative_design import CodexDesignStrategist, is_clear_design_intent  # noqa: E402
from frogent_plugin.research_service import ResearchService  # noqa: E402


def strategy(count: int = 3, constraints=()):
    hypotheses = []
    for rank in range(1, count + 1):
        hypotheses.append({
            "hypothesis_id": f"design-{rank}",
            "rank": rank,
            "recommendation": f"Make matched analogue {rank} to test a distinct liability hypothesis.",
            "rationale": "Medicinal-chemistry experience links this precise change to the stated goal.",
            "expected_benefits": ["improve the target property"],
            "tradeoffs": ["may weaken potency"],
            "failure_modes": ["the assumed liability may not control the phenotype"],
            "knowledge_bases": ["world_knowledge", "medicinal_chemistry_judgment",
                                "mechanistic_reasoning"],
            "calibration_requests": [{
                "request_id": f"identity-{rank}",
                "capability_id": "molecular.identity",
                "purpose": "verify the exact analogue identity",
                "decision_rule": "reject only if the identity is wrong",
            }, {
                "request_id": f"admet-{rank}",
                "capability_id": "admet.compare",
                "purpose": "compare the stated liability with the parent",
                "decision_rule": "downgrade when the matched prediction worsens",
            }],
            "decisive_experiment": "Synthesize the matched pair and measure potency plus clearance.",
            "confidence": "medium",
        })
    return {"objective": "Improve this lead's exposure while retaining potency.",
            "reliable_discriminator": False, "unresolved_qualitative_choices": True,
            "discriminator": "", "constraints": list(constraints),
            "optimization_handoff": {"applicable": False, "objective": "", "constraints": [],
                "search_space": "", "discriminator": "", "optimizer": "", "stopping_rule": "",
                "residual_qualitative_choices": []},
            "hypotheses": hypotheses}


class FakeClient:
    def __init__(self, value) -> None:
        self.value, self.calls = value, []

    def generate(self, role, contract, payload, *, schema):
        self.calls.append((role, contract, payload, schema))
        return self.value


class SequenceClient:
    def __init__(self, values) -> None:
        self.values, self.calls = list(values), []

    def generate(self, role, contract, payload, *, schema):
        self.calls.append((role, contract, payload, schema))
        return self.values.pop(0)


class NeverCalled:
    def __getattr__(self, name):
        raise AssertionError(f"research path must not be called: {name}")


class NeverGenerate:
    def generate(self, *args, **kwargs):
        raise AssertionError("resumed design must not call the strategist")


class FakeCalibrator:
    def calibrate(self, portfolio, message, context):
        return (
            CalibrationFinding("design-1", CalibrationOutcome.CONTRADICTION,
                               "clearance worsened", "matched assay"),
            CalibrationFinding("design-2", CalibrationOutcome.SUPPORT,
                               "clearance improved", "matched assay"),
        )


class QualitativeDesignTests(unittest.TestCase):
    def test_strategist_uses_world_knowledge_and_returns_ranked_actionable_portfolio(self) -> None:
        client = FakeClient(strategy())
        result = QualitativeDesignHandler(CodexDesignStrategist(client)).run(
            "Use medicinal chemistry experience to optimize this lead molecule.",
            ExecutionContext("chemist", "chat", "design-1", PLUGIN_ROOT),
        )
        role, contract, payload, schema = client.calls[0]
        self.assertEqual("qualitative medicinal-design strategist", role)
        self.assertIn("world knowledge", contract)
        self.assertIn("missing tools do not erase useful recommendations", contract)
        self.assertEqual(1, schema["properties"]["hypotheses"]["minItems"])
        self.assertEqual("Use medicinal chemistry experience to optimize this lead molecule.",
                         payload["request"])
        self.assertEqual("current", payload["conversation_context"][-1]["turn_id"])
        self.assertTrue(result.answer.startswith("Recommended design hypotheses"))
        self.assertEqual(3, result.answer.count("Decisive experiment:"))
        self.assertEqual("design-1", result.portfolio.hypotheses[0].hypothesis_id)

    def test_qualitative_portfolio_cannot_collapse_to_one_safe_generic_answer(self) -> None:
        handler = QualitativeDesignHandler(CodexDesignStrategist(
            SequenceClient((strategy(1), strategy(1)))))
        result = handler.run("Optimize this molecule.",
                             ExecutionContext("chemist", "chat", "d", PLUGIN_ROOT))
        self.assertIsNone(result.portfolio)
        self.assertIn("three to six hypotheses", result.answer)

    def test_semantic_validation_gets_one_structured_repair(self) -> None:
        client = SequenceClient((strategy(1), strategy(3)))
        result = QualitativeDesignHandler(CodexDesignStrategist(client)).run(
            "Optimize this lead molecule.",
            ExecutionContext("chemist", "repair-chat", "design-repair", PLUGIN_ROOT))
        self.assertEqual(2, len(client.calls))
        self.assertEqual("qualitative medicinal-design strategist repair", client.calls[1][0])
        self.assertIn("three to six hypotheses", client.calls[1][2]["validation_error"])
        self.assertEqual(3, len(result.portfolio.hypotheses))

    def test_auto_routing_selects_design_and_protects_literature_requests(self) -> None:
        handler = QualitativeDesignHandler(CodexDesignStrategist(FakeClient(strategy())))
        service = ResearchService(NeverCalled(), NeverCalled(), NeverCalled(), PLUGIN_ROOT,
                                  design_handler=handler)
        message = "请用药化经验优化这个先导分子，提出优先合成的修饰方案"
        frames = "".join(service.stream_payload("chemist", {
            "message": message, "chat_id": "design-chat", "mode": "auto"}))
        self.assertIn('"name": "design"', frames)
        self.assertIn("Recommended design hypotheses", frames)
        events = service.typed_events[("chemist", "design-chat")]
        self.assertEqual("agent.qualitative-judgment", events[1].payload["capability_id"])
        self.assertFalse(is_clear_design_intent("搜索优化这个分子的论文和文献"))

    def test_ambiguous_mentions_do_not_hijack_other_routes(self) -> None:
        self.assertFalse(is_clear_design_intent("This molecule has an interesting scaffold."))
        self.assertFalse(is_clear_design_intent("Search a molecule in the database."))
        self.assertTrue(is_clear_design_intent("Prioritize modifications for this peptide."))
        self.assertTrue(is_clear_design_intent(
            "Use your medicinal chemistry judgment to propose the first analogues."))
        self.assertTrue(is_clear_design_intent(
            "Avoid basic amines, preserve the hinge-binding core; oral exposure is the priority."))
        self.assertTrue(is_clear_design_intent("请做SAR并给出骨架跃迁方案"))

    def test_bounded_history_constraints_are_grounded_and_enter_strategist_payload(self) -> None:
        constraints = (
            {"text": "avoid basic amines", "source_turn_id": "history-0", "immutable": True},
            {"text": "preserve hinge-binding core", "source_turn_id": "history-0",
             "immutable": True},
            {"text": "oral exposure is priority", "source_turn_id": "history-0",
             "immutable": False},
        )
        client = FakeClient(strategy(constraints=constraints))
        result = QualitativeDesignHandler(CodexDesignStrategist(client)).run_with_history(
            "Use your medicinal chemistry judgment to propose the first analogues.",
            ExecutionContext("chemist", "history-chat", "design-history", PLUGIN_ROOT),
            ({"role": "user", "content":
              "avoid basic amines; preserve hinge-binding core; oral exposure is priority"},))
        self.assertEqual(3, len(result.portfolio.context.constraints))
        context = client.calls[0][2]["conversation_context"]
        self.assertEqual("history-0", context[0]["turn_id"])
        self.assertIn("User constraints: avoid basic amines (immutable)", result.answer)

    def test_structured_memory_resume_and_tool_findings_persist_reranked_portfolio(self) -> None:
        with tempfile.TemporaryDirectory(dir=PLUGIN_ROOT / "tests") as temp:
            store = SQLiteDesignStore(Path(temp) / "memory.sqlite3", PLUGIN_ROOT)
            context = ExecutionContext("chemist", "persistent-chat", "design-1", PLUGIN_ROOT)
            handler = QualitativeDesignHandler(CodexDesignStrategist(FakeClient(strategy())),
                                               store, FakeCalibrator())
            result = handler.run("Optimize this lead molecule.", context)
            self.assertEqual(("design-2", "design-3", "design-1"),
                tuple(item.hypothesis.hypothesis_id for item in result.calibrated))
            saved = store.load("chemist", "persistent-chat")
            self.assertEqual(1, saved.revision)
            self.assertEqual(2, len(saved.findings))
            resumed = QualitativeDesignHandler(CodexDesignStrategist(NeverGenerate()),
                                               store).run_with_history(
                "Optimize this lead molecule.", context,
                ({"role": "user", "content": "Optimize this lead molecule."},
                 {"role": "assistant", "content": result.answer[:2000]}))
            self.assertEqual(result.answer, resumed.answer)
            self.assertTrue(resumed.events[-1].payload["resumed"])


if __name__ == "__main__":
    unittest.main()
