"""Behavior tests for qualitative judgment and tool calibration."""

import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent.design.decision_policy import (  # noqa: E402
    CalibrationRequest,
    CalibrationFinding,
    CalibrationOutcome,
    DecisionContext,
    DesignHypothesis,
    HypothesisPortfolio,
    HypothesisState,
    OptimizationHandoff,
    OptimizationRegime,
)
from agent.design.design_calibration import calibrate_portfolio, render_portfolio  # noqa: E402


def hypothesis(identity: str, rank: int, recommendation: str) -> DesignHypothesis:
    return DesignHypothesis(
        identity,
        rank,
        recommendation,
        "This change tests a specific exposure-versus-potency design thesis.",
        ("improve the desired property",),
        ("may reduce target potency",),
        ("the assumed liability may not drive the phenotype",),
        ("world_knowledge", "medicinal_chemistry_judgment", "mechanistic_reasoning"),
        (CalibrationRequest(f"{identity}-identity", "molecular.identity",
                            "normalize identity", "reject only an identity mismatch"),
         CalibrationRequest(f"{identity}-admet", "admet.compare",
                            "compare the relevant endpoint",
                            "downgrade only when the matched comparison worsens")),
        "Synthesize the matched pair and run potency plus the liability assay.",
        "medium",
    )


class DecisionRegimeTests(unittest.TestCase):
    def test_problem_split_distinguishes_qualitative_hybrid_and_quantitative(self) -> None:
        qualitative = DecisionContext("improve oral exposure", False, True)
        hybrid = DecisionContext("improve oral exposure", True, True, "validated PK assay")
        quantitative = DecisionContext("maximize assay response", True, False,
            "validated objective-aligned assay", (),
            OptimizationHandoff("maximize assay response", ("valid structures only",),
                "current analogue space", "validated objective-aligned assay",
                "batch Bayesian optimization", "stop after converged expected improvement"))
        self.assertEqual(OptimizationRegime.QUALITATIVE, qualitative.regime)
        self.assertEqual(OptimizationRegime.HYBRID, hybrid.regime)
        self.assertEqual(OptimizationRegime.QUANTITATIVE, quantitative.regime)

    def test_unverified_discriminator_cannot_drive_quantitative_mode(self) -> None:
        with self.assertRaisesRegex(ValueError, "unverified discriminator"):
            DecisionContext("improve efficacy", False, False, "uncalibrated docking score")


class ToolCalibrationTests(unittest.TestCase):
    def setUp(self) -> None:
        context = DecisionContext("improve oral exposure without losing potency", False, True)
        self.portfolio = HypothesisPortfolio(context, (
            hypothesis("h1", 1, "Block the dominant metabolic soft spot with a matched bioisostere."),
            hypothesis("h2", 2, "Reduce one exposed lipophilic substituent while retaining shape."),
            hypothesis("h3", 3, "Constrain the active conformation with a small ring closure."),
        ))

    def test_unavailable_tools_do_not_erase_recommendations(self) -> None:
        values = calibrate_portfolio(self.portfolio, (
            CalibrationFinding("h1", CalibrationOutcome.UNAVAILABLE,
                               "metabolite identification is unavailable", "ADMET runtime"),
        ))
        self.assertEqual(HypothesisState.RECOMMENDED, values[0].state)
        self.assertEqual(3, len(values))

    def test_tools_strengthen_downgrade_or_reject_without_replacing_judgment(self) -> None:
        values = calibrate_portfolio(self.portfolio, (
            CalibrationFinding("h1", CalibrationOutcome.SUPPORT,
                               "predicted clearance improves", "ADMET"),
            CalibrationFinding("h2", CalibrationOutcome.CONTRADICTION,
                               "solubility worsens in the matched comparison", "ADMET"),
            CalibrationFinding("h3", CalibrationOutcome.HARD_BLOCK,
                               "generated structure violates the immutable stereochemical constraint",
                               "RDKit identity gate"),
        ))
        self.assertEqual((HypothesisState.STRENGTHENED, HypothesisState.DOWNGRADED,
                          HypothesisState.REJECTED), tuple(item.state for item in values))

    def test_calibration_changes_priority_while_preserving_initial_rank(self) -> None:
        values = calibrate_portfolio(self.portfolio, (
            CalibrationFinding("h1", CalibrationOutcome.CONTRADICTION,
                               "clearance worsened", "matched assay"),
            CalibrationFinding("h2", CalibrationOutcome.SUPPORT,
                               "clearance improved", "matched assay"),
        ))
        self.assertEqual(("h2", "h3", "h1"),
                         tuple(item.hypothesis.hypothesis_id for item in values))
        self.assertEqual((1, 2, 3), tuple(item.adjusted_rank for item in values))
        self.assertEqual((2, 3, 1), tuple(item.hypothesis.rank for item in values))

    def test_rendering_leads_with_ranked_actions_and_decisive_experiments(self) -> None:
        answer = render_portfolio(self.portfolio)
        self.assertTrue(answer.startswith("Recommended design hypotheses"))
        self.assertLess(answer.index("1. [recommended]"), answer.index("Tool calibration")
                        if "Tool calibration" in answer else len(answer))
        self.assertIn("Knowledge basis: world_knowledge, medicinal_chemistry_judgment", answer)
        self.assertEqual(3, answer.count("Failure mode:"))
        self.assertEqual(3, answer.count("Calibration plan:"))
        self.assertEqual(3, answer.count("Decisive experiment:"))

    def test_portfolio_requires_stable_ranked_lineage(self) -> None:
        with self.assertRaisesRegex(ValueError, "contiguous ranked order"):
            HypothesisPortfolio(self.portfolio.context, (
                hypothesis("h1", 1, "First"), hypothesis("h2", 3, "Third")))


if __name__ == "__main__":
    unittest.main()
