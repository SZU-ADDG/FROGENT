from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts import score_mdockpep2_reference_redocking as scorer


def _pdb(coords: list[tuple[float, float, float]], model: bool = False) -> str:
    lines = ["MODEL  1"] if model else []
    for index, (x, y, z) in enumerate(coords, start=1):
        lines.append(
            f"ATOM  {index:5d}  CA  ALA A{index:4d}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00           C"
        )
    if model:
        lines.append("ENDMDL")
    return "\n".join(lines) + "\n"


class MDockPeP2ReferenceScoringTests(unittest.TestCase):
    def test_direct_and_superposed_rmsd_are_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            native = root / "native.pdb"
            predicted = root / "predicted.pdb"
            native.write_text(_pdb([(0, 0, 0), (1, 0, 0), (0, 1, 0)]))
            predicted.write_text(_pdb([(10, 0, 0), (11, 0, 0), (10, 1, 0)], model=True))
            row = scorer._score_models(native, predicted)[0]
            self.assertAlmostEqual(row["receptor_frame_ca_rmsd_angstrom"], 10.0)
            self.assertAlmostEqual(row["superposed_ca_rmsd_angstrom"], 0.0, places=6)

    def test_mismatched_ca_counts_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            native = root / "native.pdb"
            predicted = root / "predicted.pdb"
            native.write_text(_pdb([(0, 0, 0), (1, 0, 0)]))
            predicted.write_text(_pdb([(0, 0, 0)], model=True))
            with self.assertRaises(ValueError):
                scorer._score_models(native, predicted)


if __name__ == "__main__":
    unittest.main()
