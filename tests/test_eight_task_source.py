from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from evaluation.benchmarks.eight_task_source import audit_source_pack


class EightTaskSourceAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self._write_fixture()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_csv(self, name: str, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
        with (self.root / name).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def _write_fixture(self) -> None:
        self._write_csv(
            "test_data1.csv",
            ["index", "question", "answer", "answer_type", "rationale", "raw_subject"],
            [
                {
                    "index": str(index),
                    "question": f"question {index}",
                    "answer": "True",
                    "answer_type": "exactMatch",
                    "rationale": "fixture rationale",
                    "raw_subject": "Biology",
                }
                for index in range(1, 21)
            ],
        )
        self._write_csv(
            "test_data2.csv",
            ["question", "answer", "smiles"],
            [{"question": f"target-{i}", "answer": "DB00001", "smiles": "CC"} for i in range(20)],
        )
        self._write_csv(
            "test_data3.csv",
            ["question", "answer"],
            [{"question": f"disease-{i}", "answer": "GENE1;GENE2"} for i in range(20)],
        )
        self._write_csv(
            "test_data4.csv",
            ["smiles", "question", "answer"],
            [
                {
                    "smiles": "CC",
                    "question": "QED;A;B;C;D",
                    "answer": "0.1;0.2;0;1;0",
                }
                for _ in range(20)
            ],
        )
        self._write_csv(
            "test_data5.csv",
            ["smiles", "questions", "pdb_id", "answer"],
            [
                {
                    "smiles": "['CC', 'CCC']",
                    "questions": f"protein-{i}",
                    "pdb_id": f"p5_{i}",
                    "answer": "CC",
                }
                for i in range(20)
            ],
        )
        self._write_csv(
            "test_data6.csv",
            ["smiles", "protein", "question", "answer"],
            [
                {
                    "smiles": "CC",
                    "protein": f"p6_{i}",
                    "question": "A;B;C;D;E",
                    "answer": "1;2;3;4;5",
                }
                for i in range(20)
            ],
        )
        self._write_csv(
            "test_data8.csv",
            ["smiles", "answer"],
            [{"smiles": "CC", "answer": "C.C -> CC"} for _ in range(20)],
        )
        for directory, prefix in (("test_data5PDB", "p5"), ("test_data6PDB", "p6")):
            path = self.root / directory
            path.mkdir()
            for index in range(20):
                (path / f"{prefix}_{index}.pdb").write_text("END\n", encoding="ascii")
        pockets = self.root / "test_data7"
        pockets.mkdir()
        for index in range(20):
            (pockets / f"pocket_{index}.pdb").write_text("END\n", encoding="ascii")
        (self.root / "test_data7_prompt.txt").write_text("Generate five molecules.", encoding="utf-8")

    def test_complete_pack_is_valid(self) -> None:
        result = audit_source_pack(self.root)
        self.assertEqual(result["task_summaries"]["virtual_screening"]["valid_cases"], 20)
        self.assertEqual(result["task_summaries"]["molecular_design"]["cases"], 20)
        self.assertTrue(result["missing_fields"]["original_scorer_code"])

    def test_gold_outside_candidate_pool_is_retained_as_invalid(self) -> None:
        path = self.root / "test_data5.csv"
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        rows[12]["answer"] = "N"
        self._write_csv(
            "test_data5.csv",
            ["smiles", "questions", "pdb_id", "answer"],
            rows,
        )
        result = audit_source_pack(self.root)
        virtual_screening = result["task_summaries"]["virtual_screening"]
        self.assertEqual(virtual_screening["attempted_cases"], 20)
        self.assertEqual(virtual_screening["valid_cases"], 19)
        self.assertEqual(virtual_screening["invalid_cases"][0]["row_index"], 13)


if __name__ == "__main__":
    unittest.main()
