from __future__ import annotations

import unittest
import json

from scripts import run_external_current_model_adaptations as runner
from scripts import run_external_current_model_recovery as recovery


class ExternalCurrentModelAdaptationTests(unittest.TestCase):
    def test_cladd_does_not_claim_disease_target_alignment(self) -> None:
        protocol = runner._load_protocol(runner.DEFAULT_RUN_ROOT)
        cladd = next(item for item in protocol["systems"] if item["name"] == "CLADD")
        self.assertEqual(cladd["alignable_tasks"], ["molecular_property_prediction"])

    def test_prompt_contains_source_commit_and_no_frogent_initialization(self) -> None:
        protocol = runner._load_protocol(runner.DEFAULT_RUN_ROOT)
        system = next(item for item in protocol["systems"] if item["name"] == "Robin")
        prompt = runner._workflow_prompt(system, "retrieve_known_targets", [1])
        self.assertIn(system["commit"], prompt)
        self.assertIn("Do not use FROGENT initialization", prompt)
        self.assertNotIn('"answer"', prompt)

    def test_task_specific_batch_sizes(self) -> None:
        self.assertEqual(runner._batch_size("Prompt-to-Pill", "molecular_design"), 1)
        self.assertEqual(runner._batch_size("Robin", "retrieve_known_drugs"), 5)
        self.assertEqual(runner._batch_size("CLADD", "molecular_property_prediction"), 10)

    def test_recovery_json_extractor_accepts_plain_and_fenced_objects(self) -> None:
        expected = {"results": [{"case_index": 1}]}
        self.assertEqual(recovery._extract_json(json.dumps(expected)), expected)
        self.assertEqual(
            recovery._extract_json("```json\n" + json.dumps(expected) + "\n```"),
            expected,
        )

    def test_recovery_json_extractor_rejects_non_object(self) -> None:
        with self.assertRaises(ValueError):
            recovery._extract_json("[]")


if __name__ == "__main__":
    unittest.main()
