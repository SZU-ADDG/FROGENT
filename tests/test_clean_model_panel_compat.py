"""Tests for transparent provider-output compatibility handling."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_clean_ten_model_panel import (  # noqa: E402
    _collapse_single_case_repetitions,
)


class CleanModelPanelCompatibilityTests(unittest.TestCase):
    def test_collapses_only_identical_single_case_duplicates(self):
        item = {"case_index": 3, "answer": "x"}
        value, collapsed, identical, out_of_scope = _collapse_single_case_repetitions(
            {"results": [item, dict(item), dict(item)]},
            [3],
        )
        self.assertEqual({"results": [item]}, value)
        self.assertEqual(2, collapsed)
        self.assertTrue(identical)
        self.assertEqual(0, out_of_scope)

    def test_keeps_first_nonidentical_repetition_without_using_gold(self):
        nonidentical = {
            "results": [
                {"case_index": 3, "answer": "x"},
                {"case_index": 3, "answer": "y"},
            ]
        }
        value, collapsed, identical, out_of_scope = _collapse_single_case_repetitions(
            nonidentical,
            [3],
        )
        self.assertEqual({"results": [{"case_index": 3, "answer": "x"}]}, value)
        self.assertEqual(1, collapsed)
        self.assertFalse(identical)
        self.assertEqual(0, out_of_scope)

    def test_preserves_multicase_or_mixed_index_results(self):
        multicase = {
            "results": [
                {"case_index": 3, "answer": "x"},
                {"case_index": 4, "answer": "y"},
            ]
        }
        value, collapsed, identical, out_of_scope = _collapse_single_case_repetitions(
            multicase,
            [3, 4],
        )
        self.assertIs(multicase, value)
        self.assertEqual(0, collapsed)
        self.assertTrue(identical)
        self.assertEqual(0, out_of_scope)

    def test_keeps_requested_case_and_discards_out_of_scope_expansion(self):
        expanded = {
            "results": [
                {"case_index": 1, "answer": "requested"},
                {"case_index": 2, "answer": "extra"},
                {"case_index": 3, "answer": "extra"},
            ]
        }
        value, collapsed, identical, out_of_scope = (
            _collapse_single_case_repetitions(expanded, [1])
        )
        self.assertEqual(
            {"results": [{"case_index": 1, "answer": "requested"}]},
            value,
        )
        self.assertEqual(2, collapsed)
        self.assertTrue(identical)
        self.assertEqual(2, out_of_scope)


if __name__ == "__main__":
    unittest.main()
