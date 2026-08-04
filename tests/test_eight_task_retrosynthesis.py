from __future__ import annotations

import json
import unittest

from scripts.analyze_eight_task_retrosynthesis import (
    _route_metrics,
    parse_predicted_routes,
    parse_reference_route,
)


class EightTaskRetrosynthesisTests(unittest.TestCase):
    def test_forward_reference_matches_retrosynthetic_prediction(self) -> None:
        reference = parse_reference_route("CC.O -> CCO")
        tool_text = json.dumps({"routes 1": "`[\"'CCO'->'CC.O'\"]`"})
        response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"content": [{"type": "text", "text": tool_text}], "isError": False},
        }
        routes = parse_predicted_routes("event: message\ndata: " + json.dumps(response) + "\n")
        metrics = _route_metrics("CCO", reference, routes)
        self.assertTrue(metrics["top1_full_exact"])
        self.assertTrue(metrics["top1_target_rooted"])

    def test_partial_route_is_counted_conservatively(self) -> None:
        reference = parse_reference_route("CC.O -> CCO | C.C -> CC")
        partial = parse_reference_route("CC.O -> CCO")
        metrics = _route_metrics("CCO", reference, (partial,))
        self.assertFalse(metrics["top1_full_exact"])
        self.assertEqual(metrics["top5_best_reference_recall"], 0.5)


if __name__ == "__main__":
    unittest.main()
