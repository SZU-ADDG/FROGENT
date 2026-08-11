#!/usr/bin/env python3
"""Run current-model adaptations of CLADD, Prompt-to-Pill and Robin."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_clean_ten_model_panel as clean_runner
from scripts import score_clean_ten_model_panel as clean_scorer


DEFAULT_RUN_ROOT = (
    ROOT
    / "runtime/evaluation/revision-20260807/"
    "external-current-model-adaptations-r01"
)

WORKFLOW_STAGES = {
    "CLADD": [
        "molecule interpreter extracts chemically meaningful features from each SMILES",
        "planner assigns each requested endpoint to a focused prediction role",
        "endpoint roles make independent predictions",
        "critic checks scale, label order and internal consistency before structured output",
    ],
    "Prompt-to-Pill": [
        "orchestrator decomposes each case into the applicable chemical-property, ADMET, screening or generation role",
        "specialist role evaluates the supplied molecular or pocket inputs",
        "cross-check role enforces the task-specific constraints",
        "orchestrator emits the frozen structured response",
    ],
    "Robin": [
        "literature-research role recalls and organizes relevant therapeutic evidence",
        "candidate-synthesis role ranks drugs or targets for the supplied biomedical entity",
        "evidence critic removes unsupported or mismatched candidates",
        "lead agent emits the frozen structured response; wet-lab execution is outside this computational cell",
    ],
}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _load_protocol(run_root: Path) -> dict[str, Any]:
    protocol_path = run_root / "protocol/protocol.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("status") != "preregistered_before_adapted_outputs":
        raise ValueError("external adaptation protocol is not preregistered")
    return protocol


def _workflow_prompt(system: dict[str, Any], task: str, indices: list[int]) -> str:
    instruction, cases = clean_runner._task_payload(task)
    selected = [case for case in cases if int(case["case_index"]) in indices]
    payload = {
        "adapted_system": system["name"],
        "source_commit": system["commit"],
        "adapted_model": system["adapted_model"],
        "workflow_stages": WORKFLOW_STAGES[system["name"]],
        "task": task,
        "instruction": instruction,
        "cases": selected,
    }
    return (
        "Execute the named public system as a current-model computational adaptation. "
        "Follow the workflow stages in order within this response. Do not use FROGENT "
        "initialization, persistent memory, hidden answers, files, tools or web search. "
        "Do not expose private reasoning; return only the JSON object required by the "
        "supplied schema and preserve every case_index exactly.\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    )


def _model_config(system: dict[str, Any]) -> dict[str, Any]:
    model_id = str(system["adapted_model"])
    return {
        "model_id": model_id,
        "allow_provider_fallbacks": True,
        "reasoning": {"effort": "medium" if "opus" in model_id else "low"},
        "max_tokens": 12000,
        "include_seed": True,
    }


def _batch_size(system_name: str, task: str) -> int:
    if task == "molecular_design":
        return 1
    if task == "virtual_screening":
        return 5
    if system_name == "Robin":
        return 5
    return 10


def _run_batch(
    system: dict[str, Any], task: str, indices: list[int], batch_root: Path
) -> dict[str, Any]:
    batch_root.mkdir(parents=True, exist_ok=False)
    outcome = clean_runner._openrouter_call(
        _model_config(system),
        task,
        _workflow_prompt(system, task, indices),
        clean_runner._schema(task, len(indices)),
        batch_root,
    )
    clean_runner._validate_result(task, outcome["response"], indices)
    return outcome


def _run_cell(run_root: Path, system: dict[str, Any], task: str) -> dict[str, Any]:
    cell_root = run_root / "raw" / _slug(system["name"]) / task
    terminal_path = cell_root / "terminal.json"
    if terminal_path.exists():
        terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
        if terminal.get("status") == "succeeded":
            return terminal
        raise RuntimeError(f"terminal cell already exists: {terminal_path}")
    cell_root.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    size = _batch_size(system["name"], task)
    batches = [list(range(start, min(start + size, 21))) for start in range(1, 21, size)]
    terminal: dict[str, Any]
    try:
        outcomes = []
        for indices in batches:
            batch_root = cell_root / f"batch-{indices[0]:02d}-{indices[-1]:02d}"
            outcomes.append((indices, _run_batch(system, task, indices, batch_root)))
        results: list[dict[str, Any]] = []
        metadata = []
        for indices, outcome in outcomes:
            results.extend(outcome["response"]["results"])
            metadata.append({"case_indices": indices, **outcome["transport_metadata"]})
        results.sort(key=lambda item: int(item["case_index"]))
        response = {"results": results}
        clean_runner._validate_result(task, response)
        terminal = {
            "status": "succeeded",
            "system": system["name"],
            "task": task,
            "response": response,
            "wall_seconds": time.monotonic() - started,
            "transport_metadata": {"batches": metadata},
        }
    except Exception as exc:
        terminal = {
            "status": "failed",
            "system": system["name"],
            "task": task,
            "wall_seconds": time.monotonic() - started,
            "error": f"{type(exc).__name__}: {exc}",
        }
    terminal_path.write_text(
        json.dumps(terminal, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return terminal


def _score(run_root: Path, protocol: dict[str, Any]) -> dict[str, Any]:
    cells = []
    for system in protocol["systems"]:
        for task in system["alignable_tasks"]:
            terminal_path = run_root / "raw" / _slug(system["name"]) / task / "terminal.json"
            record: dict[str, Any] = {
                "system": system["name"],
                "model_id": system["adapted_model"],
                "task": task,
                "status": "missing",
                "score": None,
            }
            if terminal_path.exists():
                terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
                record["status"] = terminal["status"]
                record["wall_seconds"] = terminal.get("wall_seconds")
                if terminal["status"] == "succeeded":
                    details = clean_scorer.SCORERS[task](terminal["response"])
                    values = [
                        float(row["score"])
                        for row in details
                        if isinstance(row.get("score"), (int, float))
                        and math.isfinite(float(row["score"]))
                    ]
                    record["status"] = "scored"
                    record["measured_cases"] = len(values)
                    record["score"] = sum(values) / len(values) if values else None
                else:
                    record["error"] = terminal.get("error")
            cells.append(record)
    counts = {status: sum(cell["status"] == status for cell in cells) for status in sorted({cell["status"] for cell in cells})}
    return {
        "schema_version": "frogent-external-current-model-adaptation-analysis-v1",
        "status": "complete" if all(cell["status"] == "scored" for cell in cells) else "partial",
        "cells": cells,
        "cell_counts": counts,
        "claim_boundary": "Current-model computational adaptations of public workflows on alignable exposed tasks. These values are not reproductions of the original paper-era systems or scores.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--systems", nargs="*")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--analyze-only", action="store_true")
    args = parser.parse_args()
    run_root = args.run_root.resolve()
    run_root.relative_to(ROOT)
    protocol = _load_protocol(run_root)
    selected = set(args.systems or [system["name"] for system in protocol["systems"]])
    unknown = selected - {system["name"] for system in protocol["systems"]}
    if unknown:
        raise ValueError(f"unknown systems: {sorted(unknown)}")
    if not args.analyze_only:
        jobs = [
            (system, task)
            for system in protocol["systems"]
            if system["name"] in selected
            for task in system["alignable_tasks"]
        ]
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            futures = {
                pool.submit(_run_cell, run_root, system, task): (system["name"], task)
                for system, task in jobs
            }
            for future in as_completed(futures):
                future.result()
    analysis = _score(run_root, protocol)
    analysis_root = run_root / "analysis"
    analysis_root.mkdir(exist_ok=True)
    (analysis_root / "summary.json").write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if all(cell["status"] not in {"missing", "succeeded"} for cell in analysis["cells"]):
        manifest = {
            "schema_version": "frogent-external-current-model-adaptation-final-v1",
            "status": "complete" if analysis["status"] == "complete" else "terminal_with_failures",
            "cell_counts": analysis["cell_counts"],
            "analysis_files": ["summary.json"],
            "claim_boundary": analysis["claim_boundary"],
        }
        (analysis_root / "final-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(analysis["cell_counts"], sort_keys=True))
    return 0 if analysis["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
