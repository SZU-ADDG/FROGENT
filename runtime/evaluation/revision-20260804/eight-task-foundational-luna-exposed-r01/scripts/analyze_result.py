#!/usr/bin/env python3
"""Produce deterministic descriptive slices for the completed Luna/max panel."""

import csv
import json
from collections import defaultdict
from pathlib import Path


RUN_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[5]
SOURCE = (PROJECT_ROOT / "runtime/evaluation/revision-20260804/source-material/"
          "eight-task-benchmark-r01/extracted/test_data1.csv")


def main() -> None:
    summary = json.loads((RUN_ROOT / "output/summary.json").read_text(encoding="utf-8"))
    with SOURCE.open(newline="", encoding="utf-8-sig") as handle:
        source = {int(row["index"]): row for row in csv.DictReader(handle)}
    slices: dict[str, dict[str, list[int]]] = {
        "answer_type": defaultdict(lambda: [0, 0]),
        "raw_subject": defaultdict(lambda: [0, 0]),
        "reported_confidence": defaultdict(lambda: [0, 0]),
    }
    for item in summary["per_case"]:
        index = int(item["case_index"])
        values = {
            "answer_type": item["answer_type"],
            "raw_subject": source[index]["raw_subject"],
            "reported_confidence": item["confidence"],
        }
        for dimension, label in values.items():
            slices[dimension][label][1] += 1
            slices[dimension][label][0] += int(item["correct"])
    output = {"schema_version": "frogent-eight-task-foundational-analysis-v1", "slices": {}}
    for dimension, groups in slices.items():
        output["slices"][dimension] = {
            label: {"correct": counts[0], "total": counts[1],
                    "accuracy": counts[0] / counts[1]}
            for label, counts in sorted(groups.items())
        }
    output["interpretation"] = [
        "All twenty calls returned the high confidence label, while nine were exact-correct.",
        "The high-confidence label is not calibrated as a reliable correctness indicator on this panel.",
        "Subject slices are descriptive because each group contains only two to five exposed cases."
    ]
    path = RUN_ROOT / "output/analysis.json"
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
