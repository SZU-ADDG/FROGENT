from __future__ import annotations

import unittest

from scripts.analyze_eight_task_property_admet import _binary_metrics, _regression_metrics


class EightTaskPropertyADMETScoringTests(unittest.TestCase):
    def test_binary_metrics_use_frozen_half_threshold(self) -> None:
        result = _binary_metrics([0, 0, 1, 1], [0.1, 0.8, 0.5, 0.9])
        self.assertEqual(result["confusion"], {"tp": 2, "tn": 1, "fp": 1, "fn": 0})
        self.assertEqual(result["accuracy"], 0.75)
        self.assertEqual(result["balanced_accuracy"], 0.75)

    def test_regression_metrics_preserve_direction(self) -> None:
        result = _regression_metrics([1.0, 2.0, 3.0], [1.0, 2.5, 2.5])
        self.assertAlmostEqual(result["mae"], 1 / 3)
        self.assertAlmostEqual(result["rmse"], (0.5 / 3) ** 0.5)
        self.assertGreater(result["spearman_rho"], 0)


if __name__ == "__main__":
    unittest.main()
