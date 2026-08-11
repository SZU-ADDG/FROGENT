from __future__ import annotations

import csv
import tempfile
import unittest
import zipfile
from pathlib import Path

from evaluation.benchmarks.davis_gold_replacement import (
    DavisGoldSelectionError,
    select_davis_gold_replacement,
)


class DavisGoldReplacementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.archive = self.root / "DAVIS.zip"
        self.source = self.root / "test_data5.csv"
        self._write_archive()
        self._write_source()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_archive(self, *, tied: bool = False) -> None:
        drugs = (
            "Drug_Index,CID,Canonical_SMILES,Isomeric_SMILES\n"
            "0,100,CC(O)F,C[C@H](O)F.OP(=O)(O)O\n"
            "1,200,CCC,CCC\n"
        )
        proteins = (
            "Protein_Index,Accession_Number,Gene_Name,Sequence\n"
            "7,NP_TEST,TEST_TARGET,AAAA\n"
        )
        second_affinity = "9.0" if tied else "8.0"
        affinities = (
            "Drug_Index,Protein_Index,Affinity\n"
            "0,7,9.0\n"
            f"1,7,{second_affinity}\n"
        )
        with zipfile.ZipFile(self.archive, "w") as archive:
            archive.writestr("DAVIS/drugs.csv", drugs)
            archive.writestr("DAVIS/proteins.csv", proteins)
            archive.writestr("DAVIS/drug_protein_affinity.csv", affinities)

    def _write_source(self) -> None:
        candidates = [
            "CC(O)F",
            "C",
            "CC",
            "CCC",
            "CCCC",
            "CCCCC",
            "CCCCCC",
            "N",
            "NN",
            "O",
            "OO",
        ]
        with self.source.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["smiles", "questions", "pdb_id", "answer"],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "smiles": repr(candidates),
                    "questions": "TEST_TARGET",
                    "pdb_id": "1abc",
                    "answer": "C[C@H](O)F",
                }
            )

    def test_selects_unique_top_gold_and_repairs_stereochemistry(self) -> None:
        result = select_davis_gold_replacement(
            self.archive,
            self.source,
            target_label="TEST_TARGET",
            pdb_id="1abc",
        )
        self.assertEqual(result["gold"]["pubchem_cid"], "100")
        self.assertEqual(result["gold"]["kd_nm"], 1.0)
        self.assertEqual(
            result["original_case"]["connectivity_only_match_indices_1_based"],
            [1],
        )
        self.assertEqual(result["corrected_case"]["exact_isomeric_gold_count"], 1)
        self.assertFalse(result["reporting"]["original_case_mutated"])

    def test_rejects_tied_top_affinity(self) -> None:
        self.archive.unlink()
        self._write_archive(tied=True)
        with self.assertRaises(DavisGoldSelectionError):
            select_davis_gold_replacement(
                self.archive,
                self.source,
                target_label="TEST_TARGET",
                pdb_id="1abc",
            )


if __name__ == "__main__":
    unittest.main()
