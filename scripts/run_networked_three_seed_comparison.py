#!/usr/bin/env python3
"""Run the preregistered network-enabled three-repeat comparison."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_clean_ten_model_panel as clean_runner
from scripts import run_paired_frogent_model_panel as frogent_runner
from scripts import score_clean_ten_model_panel as scorer


DEFAULT_RUN_ROOT = (
    ROOT
    / "runtime/evaluation/revision-20260807/networked-three-seed-comparison-r01"
)
FROGENT_EVIDENCE_ROOT = (
    ROOT
    / "runtime/evaluation/revision-20260805/paired-twelve-model-frogent-r20/evidence"
)
WRITE_LOCK = threading.Lock()

SOURCE_FILES: dict[str, dict[str, list[str]]] = {
    "CLADD": {
        "molecular_property_prediction": [
            "README.md",
            "CLADD.yaml",
            "multi_agent/multi_agent.py",
        ]
    },
    "Prompt-to-Pill": {
        "molecular_property_prediction": [
            "README.md",
            "Prompt_to_pill.py",
            "chemical_properties_mcp_sever.py",
            "admet_prediction_mcp_server.py",
        ],
        "virtual_screening": [
            "README.md",
            "Prompt_to_pill.py",
            "docking_mcp_server.py",
            "docking_module.py",
        ],
        "molecular_design": [
            "README.md",
            "Prompt_to_pill.py",
            "druggen_mcp_server.py",
            "mol_opt_mcp_server.py",
        ],
    },
    "Robin": {
        "retrieve_known_drugs": [
            "README.md",
            "robin/candidates.py",
            "robin/prompts.py",
            "robin/configuration.py",
        ],
        "retrieve_known_targets": [
            "README.md",
            "robin/candidates.py",
            "robin/prompts.py",
            "robin/configuration.py",
        ],
    },
}

NATIVE_TOOL_STATUS: dict[str, dict[str, Any]] = {
    "CLADD": {
        "status": "source_available_no_aligned_checkpoint_execution",
        "details": (
            "The public source, prompts, graph utilities and bundled data are available. "
            "No frozen checkpoint implements the five requested property endpoints, so the "
            "current-model cell uses the public workflow files and live public search."
        ),
    },
    "Prompt-to-Pill": {
        "status": "partially_unavailable_public_native_tools",
        "details": (
            "The native property tool import fails because pkapredict is absent; the ChemFM "
            "proxy contains a placeholder Hugging Face token; mol_opt has a preserved source "
            "indentation error. Public tool contracts and workflow files remain available."
        ),
    },
    "Robin": {
        "status": "paid_edison_service_unavailable",
        "details": (
            "Robin source and prompts are available. EDISON_API_KEY is absent, so the frozen "
            "public-web retrieval adaptation replaces only the unavailable literature service "
            "and does not claim original Edison execution."
        ),
    },
}


def _load_protocol(run_root: Path) -> dict[str, Any]:
    path = run_root / "protocol/protocol.json"
    protocol = json.loads(path.read_text(encoding="utf-8"))
    inherited = protocol.get("inherits")
    if inherited:
        inherited_path = (ROOT / str(inherited)).resolve()
        inherited_path.relative_to(ROOT.resolve())
        base = json.loads(inherited_path.read_text(encoding="utf-8"))
        overlay = {key: value for key, value in protocol.items() if key != "inherits"}
        protocol = {**base, **overlay, "inherits": str(inherited)}
    if protocol.get("status") != "preregistered_before_outputs":
        raise ValueError("comparison protocol is not preregistered")
    if len(protocol.get("seeds", [])) != 3:
        raise ValueError("comparison protocol must freeze exactly three seeds")
    return protocol


def _seed_slug(seed: int) -> str:
    return f"seed-{seed}"


def _source_bundle(system: dict[str, Any], task: str) -> dict[str, Any]:
    source_root = (ROOT / str(system["source_root"])).resolve()
    source_root.relative_to(ROOT.resolve())
    files = SOURCE_FILES[str(system["name"])][task]
    records = []
    remaining = 24000
    for relative in files:
        path = (source_root / relative).resolve()
        path.relative_to(source_root)
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="replace")
        excerpt = text[: max(0, min(8000, remaining))]
        remaining -= len(excerpt)
        records.append({
            "path": relative,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "excerpt": excerpt,
            "excerpt_truncated": len(excerpt) < len(text),
        })
    return {
        "repository": system["repository"],
        "commit": system["commit"],
        "files": records,
        "native_tool_status": NATIVE_TOOL_STATUS[str(system["name"])],
    }


def _external_prompt(
    system: dict[str, Any],
    task: str,
    indices: list[int],
    seed: int,
) -> tuple[str, dict[str, Any]]:
    instruction, cases = clean_runner._task_payload(task, allow_public_web=True)
    selected = [case for case in cases if int(case["case_index"]) in indices]
    task_offset = int(hashlib.sha256(task.encode("utf-8")).hexdigest()[:8], 16)
    random.Random(seed + task_offset).shuffle(selected)
    resources = _source_bundle(system, task)
    payload = {
        "adapted_system": system["name"],
        "adapted_model": system["adapted_model"],
        "task": task,
        "task_instruction": instruction,
        "cases": selected,
        "public_system_resources": resources,
    }
    prompt = (
        "Execute a current-model adaptation of the named public system. Use its supplied public "
        "workflow files and tool contracts as the system definition. General public live web "
        "search is available. Use only the system's public resources and public web; do not use "
        "FROGENT initialization, FROGENT tools, user-private tools, prior benchmark outputs, "
        "persistent memory, hidden answers, or gold labels. A native tool marked unavailable "
        "must remain unavailable evidence. Return only the JSON object required by the schema "
        "and preserve every case_index exactly.\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    )
    return prompt, resources


def _direct_model_config(model: dict[str, Any], task: str, seed: int) -> dict[str, Any]:
    configured = dict(model)
    configured.update({
        "allow_public_web": True,
        "seed": seed,
        "include_seed": True,
        "allow_provider_fallbacks": True,
        "max_attempts": 2,
        "max_tokens": 16000,
        "batch_size": 1 if task == "molecular_design" else 5,
        "batch_workers": 2,
    })
    if configured["transport"] == "openrouter":
        configured["omit_response_format"] = True
        configured["require_parameters"] = False
    if configured["transport"] == "codex":
        configured["reasoning_effort"] = str(configured["reasoning"]["effort"])
    return configured


def _run_direct_cell(
    run_root: Path, model: dict[str, Any], task: str, seed: int
) -> dict[str, Any]:
    seed_root = run_root / "repeats" / _seed_slug(seed) / "direct"
    return clean_runner._run_cell(
        seed_root, _direct_model_config(model, task, seed), task
    )


def _external_model_config(system: dict[str, Any], seed: int) -> dict[str, Any]:
    model_id = str(system["adapted_model"])
    config: dict[str, Any] = {
        "model_id": model_id,
        "reasoning": {"enabled": False},
        "allow_provider_fallbacks": True,
        "allow_public_web": True,
        "include_seed": True,
        "seed": seed,
        "max_tokens": 16000,
        "omit_response_format": True,
        "require_parameters": False,
    }
    if "claude-opus" in model_id:
        config["omit_reasoning"] = True
    return config


def _external_batch_size(task: str) -> int:
    return 1 if task == "molecular_design" else 5


def _run_external_cell(
    run_root: Path, system: dict[str, Any], task: str, seed: int
) -> dict[str, Any]:
    cell_root = (
        run_root
        / "repeats"
        / _seed_slug(seed)
        / "external"
        / "raw"
        / clean_runner._slug(str(system["name"]))
        / task
    )
    terminal_path = cell_root / "terminal.json"
    with WRITE_LOCK:
        if terminal_path.exists():
            terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
            return {
                "arm": "external",
                "system": system["name"],
                "task": task,
                "seed": seed,
                "status": terminal["status"],
                "existing": True,
            }
        cell_root.mkdir(parents=True, exist_ok=False)
    size = _external_batch_size(task)
    ordered = list(range(1, 21))
    task_offset = int(hashlib.sha256(task.encode("utf-8")).hexdigest()[:8], 16)
    random.Random(seed + task_offset).shuffle(ordered)
    results: list[dict[str, Any]] = []
    batches = []
    started = time.monotonic()
    terminal: dict[str, Any] = {
        "schema_version": "frogent-networked-external-cell-v1",
        "arm": "external",
        "system": system["name"],
        "model_id": system["adapted_model"],
        "task": task,
        "seed": seed,
        "status": "failed",
    }
    try:
        for number, start in enumerate(range(0, 20, size), 1):
            indices = ordered[start:start + size]
            batch_root = cell_root / (
                f"batch-{number:02d}-" + "-".join(f"{index:02d}" for index in indices)
            )
            batch_root.mkdir()
            prompt, resources = _external_prompt(system, task, indices, seed)
            (batch_root / "resource-manifest.json").write_text(
                json.dumps(resources, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            outcome = clean_runner._openrouter_call(
                _external_model_config(system, seed),
                task,
                prompt,
                clean_runner._schema(task, len(indices)),
                batch_root,
                indices,
            )
            clean_runner._validate_result(task, outcome["response"], indices)
            results.extend(outcome["response"]["results"])
            batches.append({
                "case_indices": indices,
                "resource_manifest": str(
                    (batch_root / "resource-manifest.json").relative_to(run_root)
                ),
                **outcome["transport_metadata"],
            })
        results.sort(key=lambda item: int(item["case_index"]))
        response = {"results": results}
        clean_runner._validate_result(task, response)
        terminal.update({
            "status": "succeeded",
            "response": response,
            "batches": batches,
            "wall_seconds": time.monotonic() - started,
        })
    except Exception as exc:
        terminal.update({
            "error": f"{type(exc).__name__}: {exc}",
            "batches": batches,
            "wall_seconds": time.monotonic() - started,
        })
    terminal_path.write_text(
        json.dumps(terminal, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "arm": "external",
        "system": system["name"],
        "task": task,
        "seed": seed,
        "status": terminal["status"],
        "existing": False,
    }


def _run_frogent_cell(
    run_root: Path, frogent: dict[str, Any], task: str, seed: int
) -> dict[str, Any]:
    seed_root = run_root / "repeats" / _seed_slug(seed) / "frogent"
    model = {
        "display_name": frogent["display_name"],
        "transport": frogent["transport"],
        "model_id": frogent["model_id"],
        "reasoning": frogent["reasoning"],
    }
    return frogent_runner._run_cell(
        seed_root,
        FROGENT_EVIDENCE_ROOT,
        model,
        task,
        5,
        1,
        False,
        16000,
        None,
        True,
        seed,
    )


def _terminal_path(
    run_root: Path,
    arm: str,
    name: str,
    task: str,
    seed: int,
) -> Path:
    base = run_root / "repeats" / _seed_slug(seed) / arm / "raw"
    return base / clean_runner._slug(name) / task / "terminal.json"


def _score_terminal(path: Path, task: str) -> tuple[str, float | None, int, str | None]:
    if not path.is_file():
        return "missing", None, 0, None
    terminal = json.loads(path.read_text(encoding="utf-8"))
    if terminal.get("status") != "succeeded":
        return "failed", None, 0, terminal.get("error")
    details = scorer.SCORERS[task](terminal["response"])
    values = [
        float(row["score"])
        for row in details
        if isinstance(row.get("score"), (int, float))
        and math.isfinite(float(row["score"]))
    ]
    return "scored", (sum(values) / len(values) if values else None), len(values), None


def analyze(run_root: Path, protocol: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for seed in protocol["seeds"]:
        for model in protocol["direct_models"]:
            for task in protocol["tasks"]:
                status, score, measured, error = _score_terminal(
                    _terminal_path(run_root, "direct", model["model_id"], task, seed), task
                )
                rows.append({
                    "arm": "direct",
                    "name": model["display_name"],
                    "model_id": model["model_id"],
                    "task": task,
                    "seed": seed,
                    "status": status,
                    "score": score,
                    "measured_cases": measured,
                    "error": error,
                })
        frogent = protocol["frogent"]
        for task in protocol["tasks"]:
            status, score, measured, error = _score_terminal(
                _terminal_path(run_root, "frogent", frogent["model_id"], task, seed), task
            )
            rows.append({
                "arm": "frogent",
                "name": "FROGENT",
                "model_id": frogent["model_id"],
                "task": task,
                "seed": seed,
                "status": status,
                "score": score,
                "measured_cases": measured,
                "error": error,
            })
        for system in protocol["external_systems"]:
            for task in system["alignable_tasks"]:
                status, score, measured, error = _score_terminal(
                    _terminal_path(run_root, "external", system["name"], task, seed), task
                )
                rows.append({
                    "arm": "external",
                    "name": system["name"],
                    "model_id": system["adapted_model"],
                    "task": task,
                    "seed": seed,
                    "status": status,
                    "score": score,
                    "measured_cases": measured,
                    "error": error,
                })
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (row["arm"], row["name"], row["model_id"], row["task"])
        grouped.setdefault(key, []).append(row)
    aggregates = []
    for (arm, name, model_id, task), members in sorted(grouped.items()):
        values = [float(row["score"]) for row in members if row["score"] is not None]
        aggregates.append({
            "arm": arm,
            "name": name,
            "model_id": model_id,
            "task": task,
            "repeat_scores": {str(row["seed"]): row["score"] for row in members},
            "successful_repeats": len(values),
            "mean": statistics.mean(values) if values else None,
            "sample_sd": statistics.stdev(values) if len(values) >= 2 else None,
            "measured_cases_per_repeat": {
                str(row["seed"]): row["measured_cases"] for row in members
            },
        })
    expected = 3 * (
        len(protocol["direct_models"]) * len(protocol["tasks"])
        + len(protocol["tasks"])
        + sum(len(system["alignable_tasks"]) for system in protocol["external_systems"])
    )
    counts = {
        status: sum(row["status"] == status for row in rows)
        for status in sorted({row["status"] for row in rows})
    }
    analysis = {
        "schema_version": "frogent-networked-three-seed-comparison-analysis-v1",
        "status": "complete" if counts.get("scored", 0) == expected else "partial",
        "expected_cells": expected,
        "cell_counts": counts,
        "per_repeat": rows,
        "aggregates": aggregates,
        "claim_boundary": protocol["claim_boundary"],
    }
    analysis_root = run_root / "analysis"
    analysis_root.mkdir(exist_ok=True)
    (analysis_root / "summary.json").write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (analysis_root / "per-repeat.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with (analysis_root / "aggregates.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "arm", "name", "model_id", "task", "successful_repeats", "mean", "sample_sd"
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows([{key: row[key] for key in fields} for row in aggregates])
    if analysis["status"] == "complete":
        manifest = {
            "schema_version": "frogent-networked-three-seed-comparison-final-v1",
            "status": "complete",
            "expected_cells": expected,
            "cell_counts": counts,
            "seeds": protocol["seeds"],
            "analysis_files": ["summary.json", "per-repeat.csv", "aggregates.csv"],
            "claim_boundary": protocol["claim_boundary"],
        }
        (analysis_root / "final-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return analysis


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--arms", nargs="*", choices=["direct", "frogent", "external"])
    parser.add_argument("--seeds", nargs="*", type=int)
    parser.add_argument("--models", nargs="*")
    parser.add_argument("--systems", nargs="*")
    parser.add_argument("--tasks", nargs="*", choices=sorted(clean_runner.TASK_FILES))
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--analyze-only", action="store_true")
    args = parser.parse_args()
    run_root = args.run_root.resolve()
    run_root.relative_to(ROOT.resolve())
    protocol = _load_protocol(run_root)
    arms = set(args.arms or ["direct", "frogent", "external"])
    seeds = args.seeds or protocol["seeds"]
    if not set(seeds).issubset(set(protocol["seeds"])):
        raise ValueError("requested seed is not frozen in the protocol")
    tasks = set(args.tasks or protocol["tasks"])
    models = [
        model for model in protocol["direct_models"]
        if not args.models or model["model_id"] in set(args.models)
    ]
    systems = [
        system for system in protocol["external_systems"]
        if not args.systems or system["name"] in set(args.systems)
    ]
    if args.workers < 1 or args.workers > 12:
        raise ValueError("workers must be in 1..12")
    jobs: list[tuple[str, Any, str, int]] = []
    if "direct" in arms:
        jobs.extend(
            ("direct", model, task, seed)
            for seed in seeds for model in models for task in protocol["tasks"]
            if task in tasks
        )
    if "frogent" in arms:
        jobs.extend(
            ("frogent", protocol["frogent"], task, seed)
            for seed in seeds for task in protocol["tasks"] if task in tasks
        )
    if "external" in arms:
        jobs.extend(
            ("external", system, task, seed)
            for seed in seeds for system in systems for task in system["alignable_tasks"]
            if task in tasks
        )
    results = []
    if not args.analyze_only:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {}
            for arm, subject, task, seed in jobs:
                if arm == "direct":
                    future = pool.submit(_run_direct_cell, run_root, subject, task, seed)
                elif arm == "frogent":
                    future = pool.submit(_run_frogent_cell, run_root, subject, task, seed)
                else:
                    future = pool.submit(_run_external_cell, run_root, subject, task, seed)
                futures[future] = (arm, subject, task, seed)
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
    analysis = analyze(run_root, protocol)
    failed = sum(result.get("status") != "succeeded" for result in results)
    return 0 if failed == 0 and (args.analyze_only or analysis["status"] == "complete") else 2


if __name__ == "__main__":
    raise SystemExit(main())
