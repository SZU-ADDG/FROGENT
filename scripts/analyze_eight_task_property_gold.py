#!/usr/bin/env python3
"""Recompute the deterministic QED field in the submitted eight-task pack."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from rdkit import Chem, rdBase
from rdkit.Chem import QED


def analyze(source_csv: Path) -> tuple[list[dict[str, object]], dict[str, object]]:
    with source_csv.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    details: list[dict[str, object]] = []
    for row_index, row in enumerate(rows, start=1):
        endpoints = row["question"].split(";")
        answers = row["answer"].split(";")
        if len(endpoints) != len(answers):
            raise ValueError(f"row {row_index} endpoint/answer lengths differ")
        if endpoints[0] != "QED":
            raise ValueError(f"row {row_index} does not place QED first")
        molecule = Chem.MolFromSmiles(row["smiles"])
        if molecule is None:
            raise ValueError(f"row {row_index} has invalid SMILES")
        supplied = float(answers[0])
        recomputed = float(QED.qed(molecule))
        details.append(
            {
                "row_index": row_index,
                "supplied_qed": supplied,
                "recomputed_qed": recomputed,
                "recomputed_qed_3dp": round(recomputed, 3),
                "absolute_error": abs(recomputed - supplied),
                "matches_supplied_3dp": round(recomputed, 3) == supplied,
            }
        )
    absolute_errors = [float(row["absolute_error"]) for row in details]
    summary = {
        "schema_version": "frogent-eight-task-property-gold-audit-v1",
        "source_cases": len(details),
        "valid_smiles": len(details),
        "rdkit_version": rdBase.rdkitVersion,
        "qed_recomputed_cases": len(details),
        "qed_3dp_exact_matches": sum(
            bool(row["matches_supplied_3dp"]) for row in details
        ),
        "qed_3dp_exact_rate": (
            sum(bool(row["matches_supplied_3dp"]) for row in details) / len(details)
            if details
            else math.nan
        ),
        "qed_mae_against_supplied_rounded_values": (
            sum(absolute_errors) / len(absolute_errors) if absolute_errors else math.nan
        ),
        "unverified_endpoints": [
            "Caco-2 Permeability",
            "BBBP",
            "CYP2D6-sub",
            "SR-p53",
        ],
        "claim_boundary": (
            "This audit verifies the supplied QED column as a deterministic RDKit descriptor. "
            "It does not validate the four model-dependent ADMET endpoint values or reconstruct "
            "the submitted aggregate property score."
        ),
    }
    return details, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_csv", type=Path)
    parser.add_argument("output_root", type=Path)
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    details, summary = analyze(args.source_csv)
    with (args.output_root / "qed-case-results.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(details[0]))
        writer.writeheader()
        writer.writerows(details)
    (args.output_root / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
