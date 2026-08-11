#!/usr/bin/env python3
"""Exact recovery for failed current-model external-system adaptation cells."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_clean_ten_model_panel as clean_runner
from scripts import run_external_current_model_adaptations as base_runner
from scripts import score_clean_ten_model_panel as clean_scorer


DEFAULT_SOURCE_ROOT = ROOT / (
    "runtime/evaluation/revision-20260807/external-current-model-adaptations-r01"
)
DEFAULT_RUN_ROOT = ROOT / (
    "runtime/evaluation/revision-20260807/external-current-model-adaptations-recovery-r02"
)
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"


def _extract_json(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, count=1, flags=re.I)
        text = re.sub(r"\s*```$", "", text, count=1)
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("plain JSON response is not an object")
    return value


def _plain_openrouter_call(
    model_id: str,
    task: str,
    prompt: str,
    indices: list[int],
    batch_root: Path,
) -> dict[str, Any]:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is missing")
    batch_root.mkdir(parents=True, exist_ok=False)
    schema = clean_runner._schema(task, len(indices))
    request_body = {
        "model": model_id,
        "messages": [
            {
                "role": "user",
                "content": (
                    prompt
                    + "\nThe exact output JSON Schema follows. Return one JSON object "
                    "with the top-level key results and no markdown:\n"
                    + json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
                ),
            }
        ],
        "temperature": 0,
        "max_tokens": 12000,
        "provider": {"allow_fallbacks": True, "data_collection": "deny"},
    }
    (batch_root / "request.json").write_text(
        json.dumps(request_body, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    request = urllib.request.Request(
        OPENROUTER_ENDPOINT,
        data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/FROGENT",
            "X-Title": "FROGENT external adaptation exact recovery",
        },
        method="POST",
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=1800) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenRouter HTTP {exc.code}: {body[-1600:]}") from exc
    wall = time.monotonic() - started
    (batch_root / "response.json").write_text(
        raw + ("" if raw.endswith("\n") else "\n"), encoding="utf-8"
    )
    envelope = json.loads(raw)
    content = envelope["choices"][0]["message"].get("content")
    if not isinstance(content, str):
        raise ValueError("OpenRouter response content is not a string")
    value = _extract_json(content)
    clean_runner._validate_result(task, value, indices)
    return {
        "response": value,
        "wall_seconds": wall,
        "transport_metadata": {
            "response_id": envelope.get("id"),
            "returned_model": envelope.get("model"),
            "provider": envelope.get("provider"),
            "usage": envelope.get("usage"),
            "finish_reason": envelope["choices"][0].get("finish_reason"),
            "parameter_amendment": "plain_json_without_response_format_seed_or_reasoning",
        },
    }


def _source_batch_response(source_root: Path, start: int, end: int) -> dict[str, Any]:
    path = source_root / (
        f"raw/cladd/molecular_property_prediction/batch-{start:02d}-{end:02d}/response.json"
    )
    envelope = json.loads(path.read_text(encoding="utf-8"))
    value = _extract_json(envelope["choices"][0]["message"]["content"])
    clean_runner._validate_result(
        "molecular_property_prediction", value, list(range(start, end + 1))
    )
    return value


def _write_terminal(path: Path, terminal: dict[str, Any]) -> dict[str, Any]:
    path.write_text(
        json.dumps(terminal, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return terminal


def _run_cladd(run_root: Path, source_root: Path, system: dict[str, Any]) -> dict[str, Any]:
    cell_root = run_root / "raw/cladd/molecular_property_prediction"
    terminal_path = cell_root / "terminal.json"
    if terminal_path.exists():
        return json.loads(terminal_path.read_text(encoding="utf-8"))
    cell_root.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    try:
        inherited = _source_batch_response(source_root, 1, 10)["results"]
        indices = list(range(11, 21))
        outcome = _plain_openrouter_call(
            system["adapted_model"],
            "molecular_property_prediction",
            base_runner._workflow_prompt(system, "molecular_property_prediction", indices),
            indices,
            cell_root / "retry-11-20",
        )
        response = {"results": inherited + outcome["response"]["results"]}
        clean_runner._validate_result("molecular_property_prediction", response)
        terminal = {
            "status": "succeeded",
            "system": "CLADD",
            "task": "molecular_property_prediction",
            "response": response,
            "wall_seconds": time.monotonic() - started,
            "inherited_cases": list(range(1, 11)),
            "retried_cases": indices,
            "transport_metadata": outcome["transport_metadata"],
        }
    except Exception as exc:
        terminal = {
            "status": "failed",
            "system": "CLADD",
            "task": "molecular_property_prediction",
            "wall_seconds": time.monotonic() - started,
            "error": f"{type(exc).__name__}: {exc}",
        }
    return _write_terminal(terminal_path, terminal)


def _run_robin_task(run_root: Path, system: dict[str, Any], task: str) -> dict[str, Any]:
    cell_root = run_root / "raw/robin" / task
    terminal_path = cell_root / "terminal.json"
    if terminal_path.exists():
        return json.loads(terminal_path.read_text(encoding="utf-8"))
    cell_root.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    try:
        results: list[dict[str, Any]] = []
        metadata = []
        for start in range(1, 21, 5):
            indices = list(range(start, start + 5))
            outcome = _plain_openrouter_call(
                system["adapted_model"],
                task,
                base_runner._workflow_prompt(system, task, indices),
                indices,
                cell_root / f"retry-{indices[0]:02d}-{indices[-1]:02d}",
            )
            results.extend(outcome["response"]["results"])
            metadata.append({"case_indices": indices, **outcome["transport_metadata"]})
        results.sort(key=lambda row: int(row["case_index"]))
        response = {"results": results}
        clean_runner._validate_result(task, response)
        terminal = {
            "status": "succeeded",
            "system": "Robin",
            "task": task,
            "response": response,
            "wall_seconds": time.monotonic() - started,
            "retried_cases": list(range(1, 21)),
            "transport_metadata": {"batches": metadata},
        }
    except Exception as exc:
        terminal = {
            "status": "failed",
            "system": "Robin",
            "task": task,
            "wall_seconds": time.monotonic() - started,
            "error": f"{type(exc).__name__}: {exc}",
        }
    return _write_terminal(terminal_path, terminal)


def _combined_analysis(run_root: Path, source_root: Path, source_protocol: dict[str, Any]) -> dict[str, Any]:
    cells = []
    for system in source_protocol["systems"]:
        slug = re.sub(r"[^a-z0-9]+", "-", system["name"].casefold()).strip("-")
        for task in system["alignable_tasks"]:
            selected_root = run_root if system["name"] in {"CLADD", "Robin"} else source_root
            terminal_path = selected_root / "raw" / slug / task / "terminal.json"
            terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
            record: dict[str, Any] = {
                "system": system["name"],
                "task": task,
                "model_id": system["adapted_model"],
                "source_root": str(selected_root.relative_to(ROOT)),
                "status": terminal["status"],
                "score": None,
            }
            if terminal["status"] == "succeeded":
                details = clean_scorer.SCORERS[task](terminal["response"])
                values = [
                    float(row["score"])
                    for row in details
                    if isinstance(row.get("score"), (int, float))
                ]
                record.update(
                    status="scored",
                    measured_cases=len(values),
                    score=sum(values) / len(values) if values else None,
                )
            else:
                record["error"] = terminal.get("error")
            cells.append(record)
    counts = {
        status: sum(cell["status"] == status for cell in cells)
        for status in sorted({cell["status"] for cell in cells})
    }
    return {
        "schema_version": "frogent-external-current-model-adaptation-combined-v1",
        "status": "complete" if counts == {"scored": len(cells)} else "partial",
        "cell_counts": counts,
        "cells": cells,
        "claim_boundary": (
            "Current-model computational adaptations of public workflows on alignable exposed "
            "tasks; original paper-era systems and scores were not reproduced."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    args = parser.parse_args()
    run_root = args.run_root.resolve()
    source_root = args.source_root.resolve()
    run_root.relative_to(ROOT)
    source_root.relative_to(ROOT)
    recovery_protocol = json.loads(
        (run_root / "protocol/protocol.json").read_text(encoding="utf-8")
    )
    if recovery_protocol.get("status") != "preregistered_before_recovery_outputs":
        raise ValueError("recovery protocol is not preregistered")
    source_protocol = json.loads(
        (source_root / "protocol/protocol.json").read_text(encoding="utf-8")
    )
    systems = {system["name"]: system for system in source_protocol["systems"]}
    jobs = [
        ("CLADD", "molecular_property_prediction"),
        ("Robin", "retrieve_known_drugs"),
        ("Robin", "retrieve_known_targets"),
    ]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {}
        for system_name, task in jobs:
            if system_name == "CLADD":
                future = pool.submit(_run_cladd, run_root, source_root, systems[system_name])
            else:
                future = pool.submit(_run_robin_task, run_root, systems[system_name], task)
            futures[future] = (system_name, task)
        for future in as_completed(futures):
            future.result()
    analysis = _combined_analysis(run_root, source_root, source_protocol)
    analysis_root = run_root / "analysis"
    analysis_root.mkdir(exist_ok=True)
    (analysis_root / "combined-summary.json").write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "frogent-external-current-model-adaptation-recovery-final-v1",
        "status": analysis["status"],
        "cell_counts": analysis["cell_counts"],
        "source_run": str(source_root.relative_to(ROOT)),
        "recovery_protocol": recovery_protocol,
        "analysis_files": ["combined-summary.json"],
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
