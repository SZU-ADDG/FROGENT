#!/usr/bin/env python3
"""Run and score ADMET-AI on the exposed eight-task property cases."""

from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
import math
import os
import platform
import time
from pathlib import Path
from typing import Any

from admet_ai import ADMETModel
from rdkit import Chem, rdBase
from scipy.stats import spearmanr


ENDPOINTS = {
    "Caco-2 Permeability": "Caco2_Wang",
    "BBBP": "BBB_Martins",
    "CYP2D6-sub": "CYP2D6_Substrate_CarbonMangels",
    "SR-p53": "SR-p53",
}
CLASSIFICATION = ("BBBP", "CYP2D6-sub", "SR-p53")


def _binary_metrics(gold: list[int], probability: list[float]) -> dict[str, Any]:
    predicted = [int(value >= 0.5) for value in probability]
    tp = sum(a == b == 1 for a, b in zip(gold, predicted, strict=True))
    tn = sum(a == b == 0 for a, b in zip(gold, predicted, strict=True))
    fp = sum(a == 0 and b == 1 for a, b in zip(gold, predicted, strict=True))
    fn = sum(a == 1 and b == 0 for a, b in zip(gold, predicted, strict=True))
    tpr = tp / (tp + fn) if tp + fn else math.nan
    tnr = tn / (tn + fp) if tn + fp else math.nan
    denominator = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return {
        "n": len(gold),
        "threshold": 0.5,
        "accuracy": (tp + tn) / len(gold),
        "balanced_accuracy": (tpr + tnr) / 2,
        "mcc": ((tp * tn) - (fp * fn)) / denominator if denominator else math.nan,
        "confusion": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
    }


def _regression_metrics(gold: list[float], predicted: list[float]) -> dict[str, Any]:
    errors = [b - a for a, b in zip(gold, predicted, strict=True)]
    rho = spearmanr(gold, predicted)
    return {
        "n": len(gold),
        "mae": sum(abs(value) for value in errors) / len(errors),
        "rmse": math.sqrt(sum(value * value for value in errors) / len(errors)),
        "spearman_rho": float(rho.statistic),
        "spearman_p": float(rho.pvalue),
    }


def run(source_csv: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    with source_csv.open(newline="", encoding="utf-8-sig") as handle:
        source_rows = list(csv.DictReader(handle))
    if len(source_rows) != 20:
        raise ValueError(f"expected 20 source cases, got {len(source_rows)}")

    parsed: list[tuple[str, dict[str, float]]] = []
    for index, row in enumerate(source_rows, start=1):
        labels = row["question"].split(";")
        values = row["answer"].split(";")
        if labels != ["QED", *ENDPOINTS]:
            raise ValueError(f"row {index} endpoint order differs from frozen protocol")
        if len(values) != 5 or Chem.MolFromSmiles(row["smiles"]) is None:
            raise ValueError(f"row {index} is malformed")
        parsed.append((row["smiles"], dict(zip(labels, map(float, values), strict=True))))

    started = time.perf_counter()
    frame = ADMETModel().predict(smiles=[item[0] for item in parsed])
    elapsed = time.perf_counter() - started
    records = frame.to_dict(orient="records")
    if len(records) != len(parsed):
        raise ValueError("ADMET-AI output row count differs from source cases")

    details: list[dict[str, Any]] = []
    for row_index, ((_, reference), prediction) in enumerate(
        zip(parsed, records, strict=True), start=1
    ):
        details.append({
            "row_index": row_index,
            "reference": {name: reference[name] for name in ENDPOINTS},
            "prediction": {name: float(prediction[provider]) for name, provider in ENDPOINTS.items()},
        })

    endpoint_metrics: dict[str, Any] = {}
    caco_gold = [intake[1]["Caco-2 Permeability"] for intake in parsed]
    caco_pred = [row["prediction"]["Caco-2 Permeability"] for row in details]
    endpoint_metrics["Caco-2 Permeability"] = _regression_metrics(caco_gold, caco_pred)
    for name in CLASSIFICATION:
        gold = [int(intake[1][name]) for intake in parsed]
        probability = [row["prediction"][name] for row in details]
        endpoint_metrics[name] = _binary_metrics(gold, probability)

    all_gold = [
        int(intake[1][name]) for intake in parsed for name in CLASSIFICATION
    ]
    all_probability = [
        row["prediction"][name] for row in details for name in CLASSIFICATION
    ]
    summary = {
        "schema_version": "frogent-eight-task-property-exposed-result-v1",
        "status": "complete",
        "source_classification": "author-supplied_exposed_test_data",
        "cases": len(details),
        "provider": "ADMET-AI",
        "provider_version": importlib.metadata.version("admet-ai"),
        "rdkit_version": rdBase.rdkitVersion,
        "python_version": platform.python_version(),
        "elapsed_seconds": elapsed,
        "endpoint_mapping": ENDPOINTS,
        "endpoint_metrics": endpoint_metrics,
        "pooled_classification": _binary_metrics(all_gold, all_probability),
        "qed_frozen_audit": {
            "cases": 20,
            "three_decimal_exact_matches": 20,
            "mae_against_supplied_rounded_values": 0.0002588482345713183,
        },
        "claim_boundary": (
            "Post-hoc exposed-case endpoint-level rerun. The supplied values are reference labels. "
            "These results do not reconstruct the submitted aggregate property score."
        ),
    }
    return details, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_csv", type=Path)
    parser.add_argument("output_root", type=Path)
    args = parser.parse_args()
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
    args.output_root.mkdir(parents=True, exist_ok=False)
    details, summary = run(args.source_csv)
    (args.output_root / "per-case.json").write_text(
        json.dumps(details, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output_root / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
