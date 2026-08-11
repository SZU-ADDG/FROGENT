#!/usr/bin/env python3
"""Run one preregistered Sol/max structured-retrieval optimization arm."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.research.structured_target_evidence import (
    list_target_drugbank_links,
    rank_disease_targets,
)
from scripts import run_clean_ten_model_panel as clean
from scripts import run_paired_frogent_model_panel as paired
from scripts import score_clean_ten_model_panel as scorer

BASE_EVIDENCE = ROOT / "runtime/evaluation/revision-20260805/paired-twelve-model-frogent-r20/evidence"
RUNS = {
    "retrieve_known_targets": ROOT / "runtime/evaluation/revision-20260811/frogent-sol-max-opentargets-known-target-r01",
    "retrieve_known_drugs": ROOT / "runtime/evaluation/revision-20260811/frogent-sol-max-uniprot-known-drug-r01",
}


def _write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _protocol(run_root: Path, task: str) -> dict[str, Any]:
    value = json.loads((run_root / "protocol/protocol.json").read_text(encoding="utf-8"))
    if value.get("status") != "preregistered_before_outputs" or value.get("task") != task:
        raise ValueError("run protocol is invalid")
    if (value.get("base_model"), value.get("reasoning_effort")) != ("gpt-5.6-sol", "max"):
        raise ValueError("model boundary must be gpt-5.6-sol/max")
    return value


def _retrieve(task: str, case: dict[str, Any]) -> dict[str, Any]:
    if task == "retrieve_known_targets":
        return rank_disease_targets(str(case["disease"]), max_results=10)
    return list_target_drugbank_links(str(case["protein"]), max_results=100)


def prepare(run_root: Path, task: str, workers: int) -> Path:
    evidence_root = run_root / "evidence"
    manifest = evidence_root / "manifest.json"
    if manifest.is_file():
        return evidence_root
    if evidence_root.exists():
        raise FileExistsError("partial evidence root exists without manifest")
    evidence_root.mkdir(parents=True)
    _, cases = clean._task_payload(task)
    base_rows = json.loads((BASE_EVIDENCE / f"{task}.json").read_text(encoding="utf-8"))
    base_by_index = {int(row["case_index"]): row for row in base_rows}
    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_retrieve, task, case): case for case in cases}
        for future in as_completed(futures):
            case = futures[future]
            index = int(case["case_index"])
            row = {"case_index": index, "query": case,
                   "literature_evidence": base_by_index[index]}
            try:
                row["structured_evidence"] = future.result()
                row["structured_status"] = "completed"
            except Exception as error:
                row["structured_status"] = "failed"
                row["structured_error"] = f"{type(error).__name__}: {error}"
            rows.append(row)
    rows.sort(key=lambda row: row["case_index"])
    _write(evidence_root / f"{task}.json", rows)
    failures = [row for row in rows if row["structured_status"] != "completed"]
    _write(manifest, {
        "schema_version": "frogent-structured-retrieval-evidence-v1",
        "task": task, "gold_visibility": "withheld", "cases": len(rows),
        "structured_completed": len(rows) - len(failures),
        "structured_failed": len(failures),
        "failed_case_indices": [row["case_index"] for row in failures],
        "evidence_sha256": _sha(evidence_root / f"{task}.json"),
        "base_literature_source": str(BASE_EVIDENCE.relative_to(ROOT)),
    })
    return evidence_root


def analyze(run_root: Path, task: str, protocol: dict[str, Any]) -> dict[str, Any]:
    terminal_path = run_root / "raw" / clean._slug(protocol["base_model"]) / task / "terminal.json"
    summary: dict[str, Any] = {"schema_version": "frogent-structured-retrieval-analysis-v1",
                               "task": task, "status": "missing", "score": None}
    if terminal_path.is_file():
        terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
        summary["status"] = terminal["status"]
        if terminal["status"] == "succeeded":
            details = scorer.SCORERS[task](terminal["response"])
            values = [float(row["score"]) for row in details
                      if isinstance(row.get("score"), (int, float))
                      and math.isfinite(float(row["score"]))]
            summary.update(status="complete", score=sum(values) / len(values),
                           measured_cases=len(values), case_scores=details,
                           baseline=protocol["baseline"],
                           success=bool(sum(values) / len(values) >
                                        protocol["baseline"]["external_robin_score"]))
        else:
            summary["error"] = terminal.get("error", "")
    output = run_root / "analysis"; output.mkdir(exist_ok=True)
    _write(output / "summary.json", summary)
    if summary["status"] == "complete":
        _write(output / "final-manifest.json", {
            "schema_version": "frogent-structured-retrieval-final-v1",
            "status": "complete", "task": task, "score": summary["score"],
            "model_id": protocol["base_model"],
            "reasoning_effort": protocol["reasoning_effort"],
            "success_criterion_met": summary["success"],
            "claim_boundary": protocol["claim_boundary"],
        })
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=tuple(RUNS), required=True)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--analyze-only", action="store_true")
    args = parser.parse_args()
    run_root = RUNS[args.task].resolve(); run_root.relative_to(ROOT.resolve())
    protocol = _protocol(run_root, args.task)
    evidence = prepare(run_root, args.task, args.workers)
    if args.prepare_only:
        return 0
    if not args.analyze_only:
        model = {"display_name": "FROGENT", "transport": "codex",
                 "model_id": protocol["base_model"],
                 "reasoning": {"effort": protocol["reasoning_effort"]}}
        paired._run_cell(run_root, evidence, model, args.task, 5, 1, False,
                         12000, None, True, None)
    result = analyze(run_root, args.task, protocol)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if result["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
