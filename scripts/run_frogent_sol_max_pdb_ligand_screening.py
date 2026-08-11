#!/usr/bin/env python3
"""Run and score the preregistered PDB-ligand-aware screening arm."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_paired_frogent_model_panel as paired
from scripts import score_clean_ten_model_panel as scorer

RUN_ROOT = ROOT / "runtime/evaluation/revision-20260811/frogent-sol-max-pdb-ligand-screening-r01"


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def main() -> int:
    protocol = json.loads((RUN_ROOT / "protocol/protocol.json").read_text())
    if protocol["status"] != "preregistered_before_full_pdb_ligand_outputs":
        raise ValueError("protocol is not preregistered")
    result = paired._run_cell(
        RUN_ROOT, RUN_ROOT / "evidence",
        {"display_name": "FROGENT", "transport": "codex",
         "model_id": protocol["base_model"],
         "reasoning": {"effort": protocol["reasoning_effort"]}},
        "virtual_screening", 5, 1, False, 12000, None, False, None,
    )
    print(json.dumps(result), flush=True)
    terminal = json.loads((RUN_ROOT / "raw/gpt-5-6-sol/virtual_screening/terminal.json").read_text())
    if terminal["status"] != "succeeded":
        return 2
    details = scorer._score_screening(terminal["response"])
    measured = [row for row in details if row["score"] is not None]
    score = sum(float(row["score"]) for row in measured) / len(measured)
    baseline = json.loads((ROOT / protocol["frozen_baseline_run"] /
                           "analysis/summary.json").read_text())
    baseline_score = next(row["score"] for row in baseline["cells"]
                          if row["task"] == "virtual_screening")
    summary = {
        "schema_version": "frogent-sol-max-pdb-ligand-screening-analysis-v1",
        "status": "complete", "score": score, "measured_cases": len(measured),
        "baseline_score": baseline_score, "paired_score_delta": score - baseline_score,
        "correct_cases": [row["case_index"] for row in measured if row["score"] == 1],
        "incorrect_cases": [row["case_index"] for row in measured if row["score"] == 0],
        "claim_boundary": protocol["claim_boundary"],
    }
    write(RUN_ROOT / "analysis/summary.json", summary)
    write(RUN_ROOT / "analysis/final-manifest.json", {
        "schema_version": "frogent-sol-max-pdb-ligand-screening-final-v1",
        "status": "complete", "model_id": protocol["base_model"],
        "reasoning_effort": protocol["reasoning_effort"], "score": score,
        "measured_cases": len(measured), "success_criterion_met": score > 17 / 19,
        "claim_boundary": protocol["claim_boundary"],
    })
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
