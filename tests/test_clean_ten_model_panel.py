"""Regression tests for the clean ten-model benchmark harness."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


RUNNER = _load("clean_panel_runner", ROOT / "scripts/run_clean_ten_model_panel.py")
SCORER = _load("clean_panel_scorer", ROOT / "scripts/score_clean_ten_model_panel.py")


class CleanPanelRunnerTest(unittest.TestCase):
    def test_all_task_payloads_have_twenty_gold_free_cases(self):
        for task in RUNNER.TASK_FILES:
            _, cases = RUNNER._task_payload(task)
            self.assertEqual(len(cases), 20, task)
            self.assertEqual(
                sorted(case["case_index"] for case in cases), list(range(1, 21)), task
            )
            for case in cases:
                self.assertNotIn("answer", case)
                self.assertNotIn("gold", case)

    def test_chunk_schema_and_validation_use_expected_indices(self):
        schema = RUNNER._schema("retrieve_known_drugs", 5)
        items = schema["properties"]["results"]
        self.assertEqual(items["minItems"], 5)
        self.assertEqual(items["maxItems"], 5)
        value = {
            "results": [
                {"case_index": index, "drugbank_ids": [], "smiles": []}
                for index in range(6, 11)
            ]
        }
        RUNNER._validate_result("retrieve_known_drugs", value, list(range(6, 11)))

    def test_clean_prompt_declares_isolation_boundary(self):
        prompt = RUNNER._prompt("foundational_biomedical_knowledge", {1})
        for phrase in ("Do not use tools", "web search", "persistent memory",
                       "prior FROGENT instructions"):
            self.assertIn(phrase, prompt)


class CleanPanelScorerTest(unittest.TestCase):
    def test_successful_recovery_precedes_failed_primary(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            temporary_root = Path(temporary)
            primary = temporary_root / "primary"
            recovery = temporary_root / "recovery"
            relative = Path("raw/example-model/example-task/terminal.json")
            for root, status in ((primary, "failed"), (recovery, "succeeded")):
                path = root / relative
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps({"status": status}), encoding="utf-8")
            root, terminal = SCORER._select_terminal(
                [primary, recovery], "example/model", "example-task"
            )
            self.assertEqual(root, recovery)
            self.assertEqual(terminal["status"], "succeeded")


if __name__ == "__main__":
    unittest.main()
