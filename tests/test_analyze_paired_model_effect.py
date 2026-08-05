"""Tests for paired case-level FROGENT effect statistics."""

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from analyze_paired_model_effect import (  # noqa: E402
    _cluster_bootstrap,
    _paired_case_statistics,
)


class PairedModelEffectStatisticsTests(unittest.TestCase):
    def test_cluster_bootstrap_is_deterministic_and_preserves_constant_delta(self):
        result = _cluster_bootstrap(
            {1: 0.2, 2: 0.2, 3: 0.2},
            {1: "a", 2: "a", 3: "b"},
            rng=np.random.default_rng(7),
            iterations=200,
        )
        self.assertAlmostEqual(0.2, result["observed_mean_delta"])
        self.assertAlmostEqual(0.2, result["ci95"][0])
        self.assertAlmostEqual(0.2, result["ci95"][1])
        self.assertEqual(2, result["clusters"])
        self.assertEqual(3, result["cases"])

    def test_case_statistics_pair_exact_model_task_case_keys(self):
        direct = []
        frogent = []
        for model_id in ("m1", "m2"):
            for case_index, score in ((1, 0.1), (2, 0.4)):
                base = {
                    "model_id": model_id,
                    "display_name": model_id,
                    "task": "foundational_biomedical_knowledge",
                    "case_index": case_index,
                    "score": score,
                }
                direct.append(base)
                frogent.append({**base, "score": score + 0.2})
        rows, statistics = _paired_case_statistics(
            direct,
            frogent,
            ["foundational_biomedical_knowledge"],
            iterations=200,
        )
        self.assertEqual(2, len(rows))
        self.assertTrue(all(row["paired_models"] == 2 for row in rows))
        self.assertTrue(all(abs(row["mean_delta"] - 0.2) < 1e-12 for row in rows))
        self.assertAlmostEqual(
            0.2,
            statistics["overall"]["observed_mean_delta"],
        )
        self.assertEqual(2, statistics["overall"]["case_task_units"])


if __name__ == "__main__":
    unittest.main()
