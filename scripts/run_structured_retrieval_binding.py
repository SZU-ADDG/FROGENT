#!/usr/bin/env python3
"""Apply preregistered deterministic binding for exact structured lookup tasks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import score_clean_ten_model_panel as scorer

RUNS = {
    "retrieve_known_targets": ROOT / "runtime/evaluation/revision-20260811/frogent-structured-binding-known-target-r02",
    "retrieve_known_drugs": ROOT / "runtime/evaluation/revision-20260811/frogent-structured-binding-known-drug-r02",
}


def _write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def bind(task: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    results = []
    for row in rows:
        evidence = row.get("structured_evidence") or {}
        records = evidence.get("results") or []
        if task == "retrieve_known_targets":
            results.append({"case_index": row["case_index"],
                            "targets": [item["symbol"] for item in records[:3]]})
        else:
            results.append({"case_index": row["case_index"],
                            "drugbank_ids": [item["drugbank_id"] for item in records[:5]],
                            "smiles": []})
    return {"results": results}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=tuple(RUNS), required=True)
    args = parser.parse_args()
    run_root = RUNS[args.task]
    protocol = json.loads((run_root / "protocol/protocol.json").read_text(encoding="utf-8"))
    if protocol.get("status") != "posthoc_amendment_preregistered_before_r02_outputs":
        raise ValueError("r02 amendment is not frozen")
    source = (ROOT / protocol["source_evidence"]).resolve(); source.relative_to(ROOT.resolve())
    rows = json.loads(source.read_text(encoding="utf-8"))
    response = bind(args.task, rows)
    raw = run_root / "raw"; raw.mkdir(exist_ok=True)
    _write(raw / "terminal.json", {"status": "succeeded", "response": response,
           "execution": "deterministic typed provider binding", "model_calls": 0})
    details = scorer.SCORERS[args.task](response)
    score = sum(float(row["score"]) for row in details) / len(details)
    analysis = run_root / "analysis"; analysis.mkdir(exist_ok=True)
    summary = {"schema_version": "frogent-structured-binding-analysis-v1",
               "status": "complete", "task": args.task, "score": score,
               "measured_cases": len(details), "case_scores": details,
               "model_calls": 0, "claim_boundary": protocol["claim_boundary"]}
    _write(analysis / "summary.json", summary)
    _write(analysis / "final-manifest.json", {
        "schema_version": "frogent-structured-binding-final-v1", "status": "complete",
        "task": args.task, "score": score, "measured_cases": len(details),
        "model_calls": 0, "claim_boundary": protocol["claim_boundary"],
    })
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
