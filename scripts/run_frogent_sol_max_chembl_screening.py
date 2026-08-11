#!/usr/bin/env python3
"""Run and score the preregistered Sol/max target-aware screening arm."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_clean_ten_model_panel as clean
from scripts import run_paired_frogent_model_panel as paired
from scripts import score_clean_ten_model_panel as scorer

DEFAULT_RUN_ROOT = ROOT / "runtime/evaluation/revision-20260811/frogent-sol-max-chembl-screening-r01"


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def analyze(run_root: Path, protocol: dict[str, Any]) -> dict[str, Any]:
    terminal_path = run_root / "raw/gpt-5-6-sol/virtual_screening/terminal.json"
    result: dict[str, Any] = {
        "schema_version": "frogent-sol-max-chembl-screening-analysis-v1",
        "status": "partial",
        "score": None,
        "measured_cases": 0,
        "claim_boundary": protocol["claim_boundary"],
    }
    if terminal_path.exists():
        terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
        result["terminal_status"] = terminal["status"]
        if terminal["status"] == "succeeded":
            details = scorer._score_screening(terminal["response"])
            values = [
                float(row["score"])
                for row in details
                if isinstance(row.get("score"), (int, float))
                and math.isfinite(float(row["score"]))
            ]
            result.update(
                status="complete",
                score=sum(values) / len(values),
                measured_cases=len(values),
                correct_cases=[row["case_index"] for row in details if row["score"] == 1],
                incorrect_cases=[row["case_index"] for row in details if row["score"] == 0],
                invalid_source_cases=[
                    row["case_index"] for row in details if row["score"] is None
                ],
            )
    analysis_root = run_root / "analysis"
    _write_json(analysis_root / "summary.json", result)
    if result["status"] == "complete":
        baseline_path = ROOT / protocol["frozen_baseline_run"] / "analysis/summary.json"
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        baseline_cell = next(
            row for row in baseline["cells"] if row["task"] == "virtual_screening"
        )
        comparison = {
            "schema_version": "frogent-target-aware-screening-comparison-v1",
            "status": "complete",
            "descriptor_only_score": baseline_cell["score"],
            "target_aware_score": result["score"],
            "paired_score_delta": result["score"] - baseline_cell["score"],
            "measured_cases": result["measured_cases"],
            "claim_boundary": protocol["claim_boundary"],
        }
        _write_json(analysis_root / "baseline-comparison.json", comparison)
        _write_json(analysis_root / "final-manifest.json", {
            "schema_version": "frogent-sol-max-chembl-screening-final-v1",
            "status": "complete",
            "model_id": protocol["base_model"],
            "reasoning_effort": protocol["reasoning_effort"],
            "task": protocol["task"],
            "score": result["score"],
            "measured_cases": result["measured_cases"],
            "claim_boundary": protocol["claim_boundary"],
        })
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--analyze-only", action="store_true")
    args = parser.parse_args()
    run_root = args.run_root.resolve()
    run_root.relative_to(ROOT.resolve())
    protocol = json.loads((run_root / "protocol/protocol.json").read_text(encoding="utf-8"))
    if protocol.get("status") != "preregistered_before_target_active_outputs":
        raise ValueError("protocol is not preregistered")
    if not (run_root / "evidence/manifest.json").exists():
        raise FileNotFoundError("target-active evidence manifest is missing")
    if not args.analyze_only:
        result = paired._run_cell(
            run_root,
            run_root / "evidence",
            {
                "display_name": "FROGENT",
                "transport": "codex",
                "model_id": protocol["base_model"],
                "reasoning": {"effort": protocol["reasoning_effort"]},
            },
            protocol["task"],
            protocol["execution"]["batch_size"],
            1,
            False,
            12000,
            None,
            False,
            None,
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
    summary = analyze(run_root, protocol)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True), flush=True)
    return 0 if summary["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
