#!/usr/bin/env python3
"""Run the frozen Chinese-model Direct OpenRouter panel with batch recovery."""

from __future__ import annotations

import argparse
import csv
import json
import math
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

from scripts import run_clean_ten_model_panel as clean
from scripts import score_clean_ten_model_panel as scorer

DEFAULT_RUN_ROOT = ROOT / "runtime/evaluation/revision-20260809/networked-eight-task-chinese-model-recovery-r03"
RECOVERY_SOURCE = ROOT / "runtime/evaluation/revision-20260807/networked-three-seed-comparison-recovery-r02"
WRITE_LOCK = threading.Lock()
PRINT_LOCK = threading.Lock()
BUDGET_STOP = threading.Event()


class BudgetExhausted(RuntimeError):
    """Stop every pending provider request after the first HTTP 402."""


def _load_protocol(run_root: Path) -> dict[str, Any]:
    protocol = json.loads((run_root / "protocol/protocol.json").read_text(encoding="utf-8"))
    if protocol.get("status") != "preregistered_before_outputs":
        raise ValueError("protocol must be preregistered before outputs")
    if len(protocol.get("seeds", [])) != 3 or len(protocol.get("tasks", [])) != 8:
        raise ValueError("protocol must freeze three seeds and eight tasks")
    if len(protocol.get("models", [])) != 9:
        raise ValueError("protocol must freeze nine Chinese models")
    return protocol


def _emit(payload: dict[str, Any]) -> None:
    with PRINT_LOCK:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True), flush=True)


def _model_config(model: dict[str, Any], seed: int) -> dict[str, Any]:
    config = dict(model)
    config.update({
        "allow_public_web": True,
        "allow_provider_fallbacks": True,
        "require_parameters": False,
        "omit_response_format": True,
        "include_seed": True,
        "seed": seed,
        "max_tokens": 16000,
    })
    return config


def _reuse_batch(model_id: str, task: str, seed: int, indices: list[int]) -> tuple[dict[str, Any], Path] | None:
    if seed != 20260807 or task not in {
        "molecular_property_prediction", "virtual_screening", "molecular_design",
        "retrieve_known_drugs", "retrieve_known_targets",
    }:
        return None
    source = (
        RECOVERY_SOURCE / "repeats" / f"seed-{seed}" / "direct" / "raw"
        / clean._slug(model_id) / task / f"batch-{indices[0]:02d}-{indices[-1]:02d}"
    )
    for response_path in sorted(source.glob("attempt-*/response.json"), reverse=True):
        try:
            envelope = json.loads(response_path.read_text(encoding="utf-8"))
            content = envelope["choices"][0]["message"]["content"]
            value, metadata = clean._decode_provider_content(task, content, indices)
        except Exception:
            continue
        return {
            "response": value,
            "wall_seconds": 0.0,
            "transport_metadata": {
                **metadata,
                "reused": True,
                "source_response": str(response_path.relative_to(ROOT)),
            },
        }, response_path
    return None


def _run_batch(
    run_root: Path, cell_root: Path, model: dict[str, Any], task: str, seed: int,
    indices: list[int], max_attempts: int,
) -> tuple[list[int], dict[str, Any]]:
    if BUDGET_STOP.is_set():
        raise BudgetExhausted("global OpenRouter budget stop is active")
    batch_root = cell_root / f"batch-{indices[0]:02d}-{indices[-1]:02d}"
    batch_root.mkdir()
    reused = _reuse_batch(str(model["model_id"]), task, seed, indices)
    if reused is not None:
        outcome, source_path = reused
        (batch_root / "reuse.json").write_text(json.dumps({
            "source_response": str(source_path.relative_to(ROOT)),
            "normalization": "transport packaging only; semantic values unchanged",
        }, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (batch_root / "normalized-response.json").write_text(
            json.dumps(outcome["response"], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _emit({"event": "batch_reused", "model_id": model["model_id"], "task": task,
               "seed": seed, "indices": indices})
        return indices, outcome
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        if BUDGET_STOP.is_set():
            raise BudgetExhausted("global OpenRouter budget stop is active")
        attempt_root = batch_root / f"attempt-{attempt:02d}"
        attempt_root.mkdir()
        try:
            outcome = clean._openrouter_call(
                _model_config(model, seed), task,
                clean._prompt(task, set(indices), allow_public_web=True, case_order_seed=seed),
                clean._schema(task, len(indices)), attempt_root, indices,
            )
            clean._validate_result(task, outcome["response"], indices)
            outcome["transport_metadata"]["request_attempts"] = attempt
            _emit({"event": "batch_succeeded", "model_id": model["model_id"], "task": task,
                   "seed": seed, "indices": indices, "attempt": attempt})
            return indices, outcome
        except Exception as exc:
            last_error = exc
            (attempt_root / "error.txt").write_text(
                f"{type(exc).__name__}: {exc}\n", encoding="utf-8"
            )
            _emit({"event": "batch_attempt_failed", "model_id": model["model_id"],
                   "task": task, "seed": seed, "indices": indices, "attempt": attempt,
                   "error": f"{type(exc).__name__}: {exc}"})
            if "OpenRouter HTTP 402" in str(exc):
                BUDGET_STOP.set()
                _emit({"event": "global_budget_stop", "model_id": model["model_id"],
                       "task": task, "seed": seed, "indices": indices})
                raise BudgetExhausted(str(exc)) from exc
            if attempt < max_attempts:
                time.sleep(2 ** (attempt - 1))
    raise RuntimeError(f"batch failed after {max_attempts} attempts: {last_error}")


def _run_cell(
    run_root: Path, model: dict[str, Any], task: str, seed: int,
    batch_workers: int, max_attempts: int,
) -> dict[str, Any]:
    if BUDGET_STOP.is_set():
        return {"event": "cell_not_started_budget_stop", "model_id": model["model_id"],
                "task": task, "seed": seed, "status": "not_started_budget_stop"}
    cell_root = (
        run_root / "repeats" / f"seed-{seed}" / "direct" / "raw"
        / clean._slug(str(model["model_id"])) / task
    )
    terminal_path = cell_root / "terminal.json"
    with WRITE_LOCK:
        if terminal_path.is_file():
            terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
            return {"model_id": model["model_id"], "task": task, "seed": seed,
                    "status": terminal["status"], "existing": True}
        cell_root.mkdir(parents=True)
    size = 1 if task == "molecular_design" else 5
    batches = [list(range(start, min(start + size, 21))) for start in range(1, 21, size)]
    terminal: dict[str, Any] = {
        "schema_version": "frogent-networked-chinese-direct-cell-v1",
        "model_id": model["model_id"], "display_name": model["display_name"],
        "transport": "openrouter", "task": task, "seed": seed, "status": "failed",
    }
    started = time.monotonic()
    outcomes: list[tuple[list[int], dict[str, Any]]] = []
    try:
        with ThreadPoolExecutor(max_workers=batch_workers) as pool:
            futures = {
                pool.submit(_run_batch, run_root, cell_root, model, task, seed, indices,
                            max_attempts): indices
                for indices in batches
            }
            for future in as_completed(futures):
                outcomes.append(future.result())
        results: list[dict[str, Any]] = []
        metadata = []
        for indices, outcome in sorted(outcomes, key=lambda item: item[0][0]):
            results.extend(outcome["response"]["results"])
            metadata.append({"case_indices": indices, **outcome["transport_metadata"]})
        results.sort(key=lambda item: int(item["case_index"]))
        response = {"results": results}
        clean._validate_result(task, response)
        terminal.update({"status": "succeeded", "response": response, "batches": metadata})
    except BudgetExhausted as exc:
        terminal["status"] = "stopped_budget"
        terminal["error"] = f"{type(exc).__name__}: {exc}"
    except Exception as exc:
        terminal["error"] = f"{type(exc).__name__}: {exc}"
    terminal["wall_seconds"] = time.monotonic() - started
    terminal_path.write_text(
        json.dumps(terminal, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    result = {"event": "cell_terminal", "model_id": model["model_id"], "task": task,
              "seed": seed, "status": terminal["status"], "existing": False}
    _emit(result)
    return result


def _terminal_path(run_root: Path, model_id: str, task: str, seed: int) -> Path:
    return (run_root / "repeats" / f"seed-{seed}" / "direct" / "raw"
            / clean._slug(model_id) / task / "terminal.json")


def analyze(run_root: Path, protocol: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for model in protocol["models"]:
        for task in protocol["tasks"]:
            for seed in protocol["seeds"]:
                path = _terminal_path(run_root, model["model_id"], task, seed)
                status, score, measured, error = "missing", None, 0, None
                if path.is_file():
                    terminal = json.loads(path.read_text(encoding="utf-8"))
                    if terminal.get("status") == "succeeded":
                        details = scorer.SCORERS[task](terminal["response"])
                        values = [float(row["score"]) for row in details
                                  if isinstance(row.get("score"), (int, float))
                                  and math.isfinite(float(row["score"]))]
                        status, measured = "scored", len(values)
                        score = sum(values) / len(values) if values else None
                    else:
                        status, error = "failed", terminal.get("error")
                rows.append({"model_id": model["model_id"], "display_name": model["display_name"],
                             "task": task, "seed": seed, "status": status, "score": score,
                             "measured_cases": measured, "error": error})
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault((row["model_id"], row["task"]), []).append(row)
    aggregates = []
    for (model_id, task), members in sorted(groups.items()):
        values = [float(row["score"]) for row in members if row["score"] is not None]
        aggregates.append({"model_id": model_id, "task": task,
                           "successful_repeats": len(values),
                           "mean": statistics.mean(values) if values else None,
                           "sample_sd": statistics.stdev(values) if len(values) > 1 else None})
    expected = len(protocol["models"]) * len(protocol["tasks"]) * len(protocol["seeds"])
    counts = {status: sum(row["status"] == status for row in rows)
              for status in ("scored", "failed", "missing")}
    analysis = {"schema_version": "frogent-networked-chinese-panel-analysis-v1",
                "status": "complete" if counts["scored"] == expected else "partial",
                "expected_cells": expected, "cell_counts": counts,
                "per_repeat": rows, "aggregates": aggregates,
                "claim_boundary": protocol["claim_boundary"]}
    analysis_root = run_root / "analysis"
    analysis_root.mkdir(exist_ok=True)
    (analysis_root / "summary.json").write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    with (analysis_root / "per-repeat.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    if analysis["status"] == "complete":
        (analysis_root / "final-manifest.json").write_text(json.dumps({
            "schema_version": "frogent-networked-chinese-panel-final-v1",
            "status": "complete", "expected_cells": expected, "cell_counts": counts,
            "seeds": protocol["seeds"], "tasks": protocol["tasks"],
        }, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return analysis


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--batch-workers", type=int, default=2)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--analyze-only", action="store_true")
    args = parser.parse_args()
    run_root = args.run_root.resolve(); run_root.relative_to(ROOT.resolve())
    if not 1 <= args.workers <= 12 or not 1 <= args.batch_workers <= 4:
        raise ValueError("workers out of frozen safety range")
    protocol = _load_protocol(run_root)
    results = []
    if not args.analyze_only:
        jobs = [(model, task, seed) for seed in protocol["seeds"]
                for model in protocol["models"] for task in protocol["tasks"]]
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(_run_cell, run_root, model, task, seed,
                                   args.batch_workers, args.max_attempts)
                       for model, task, seed in jobs]
            results = [future.result() for future in as_completed(futures)]
    analysis = analyze(run_root, protocol)
    failed = sum(result.get("status") != "succeeded" for result in results)
    return 0 if failed == 0 and analysis["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
