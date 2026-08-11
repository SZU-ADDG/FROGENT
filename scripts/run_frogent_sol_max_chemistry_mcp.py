#!/usr/bin/env python3
"""Run the preregistered Sol/max FROGENT chemistry-MCP comparison arm."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_clean_ten_model_panel as clean
from scripts import run_paired_frogent_model_panel as paired
from scripts import score_clean_ten_model_panel as scorer

DEFAULT_RUN_ROOT = ROOT / "runtime/evaluation/revision-20260811/frogent-sol-max-chemistry-mcp-r01"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_protocol(run_root: Path) -> dict[str, Any]:
    protocol = json.loads((run_root / "protocol/protocol.json").read_text(encoding="utf-8"))
    if protocol.get("status") != "preregistered_before_outputs":
        raise ValueError("protocol is not preregistered")
    if (protocol.get("base_model"), protocol.get("reasoning_effort")) != ("gpt-5.6-sol", "max"):
        raise ValueError("model boundary must be gpt-5.6-sol/max")
    if len(protocol.get("tasks", ())) != 5:
        raise ValueError("protocol must freeze five unique aligned tasks")
    return protocol


def _describe(smiles: list[str]) -> list[dict[str, Any]]:
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
            "name": "describe_molecules", "arguments": {"smiles": smiles}
        }},
    ]
    completed = subprocess.run(
        ["python3", "./scripts/launch_chemistry_mcp.py"],
        input="\n".join(json.dumps(row) for row in requests) + "\n",
        text=True, capture_output=True, cwd=ROOT, check=False,
    )
    responses = [json.loads(line) for line in completed.stdout.splitlines()]
    if completed.returncode or len(responses) != 2 or "error" in responses[1]:
        raise RuntimeError(f"chemistry MCP failed: {completed.stderr[-800:]}")
    result = responses[1].get("result", {})
    if result.get("isError"):
        raise RuntimeError(result.get("content", [{"text": "unknown MCP error"}])[0]["text"])
    values = result.get("structuredContent", {}).get("results", [])
    if len(values) != len(smiles):
        raise RuntimeError("chemistry MCP result count mismatch")
    return values


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def prepare_evidence(run_root: Path, protocol: dict[str, Any]) -> Path:
    evidence_root = run_root / "evidence"
    manifest_path = evidence_root / "manifest.json"
    if manifest_path.is_file():
        return evidence_root
    if evidence_root.exists():
        raise FileExistsError("partial evidence root exists without a manifest")
    evidence_root.mkdir(parents=True)
    base_root = (ROOT / protocol["base_evidence_source"]).resolve()
    base_root.relative_to(ROOT.resolve())
    property_base = json.loads((base_root / "molecular_property_prediction.json").read_text(
        encoding="utf-8"))
    admet_by_index = {int(row["case_index"]): row["admet_ai_2_0_1"] for row in property_base}
    _, property_cases = clean._task_payload("molecular_property_prediction")
    property_descriptors = _describe([str(case["smiles"]) for case in property_cases])
    evidence: dict[str, list[dict[str, Any]]] = {
        "molecular_property_prediction": [
            {"case_index": int(case["case_index"]),
             "admet_ai_2_0_1": admet_by_index[int(case["case_index"])],
             "chemistry_mcp": descriptor}
            for case, descriptor in zip(property_cases, property_descriptors, strict=True)
        ]
    }
    _, screening_cases = clean._task_payload("virtual_screening")
    evidence["virtual_screening"] = [
        {"case_index": int(case["case_index"]),
         "candidate_chemistry_mcp": _describe(list(case["candidate_smiles"])),
         "limitation": "Deterministic descriptors are triage signals, not docking affinity."}
        for case in screening_cases
    ]
    for task in ("molecular_design", "retrieve_known_drugs", "retrieve_known_targets"):
        evidence[task] = json.loads((base_root / f"{task}.json").read_text(encoding="utf-8"))
    for task, rows in evidence.items():
        _write_json(evidence_root / f"{task}.json", rows)
    telemetry = {
        "schema_version": "frogent-sol-max-chemistry-mcp-telemetry-v1",
        "describe_molecules_calls": 1 + len(screening_cases),
        "described_molecules": len(property_cases) + sum(
            len(case["candidate_smiles"]) for case in screening_cases),
        "rank_molecular_similarity_calls": 0,
        "similarity_skip_reason": "no explicit non-gold reference molecule in aligned inputs",
    }
    _write_json(evidence_root / "mcp-telemetry.json", telemetry)
    manifest = {
        "schema_version": "frogent-sol-max-tool-evidence-v1",
        "gold_visibility": "withheld",
        "tools": {
            "chemistry": "FROGENT chemistry stdio MCP / RDKit deterministic descriptors",
            "admet": "frozen ADMET-AI 2.0.1 evidence",
            "retrieval": "frozen gold-blind Europe PMC evidence",
            "design": "frozen deterministic pocket summaries",
        },
        "tasks": {task: {"cases": len(rows), "sha256": _sha256(evidence_root / f"{task}.json")}
                  for task, rows in evidence.items()},
        "mcp_telemetry_sha256": _sha256(evidence_root / "mcp-telemetry.json"),
    }
    _write_json(manifest_path, manifest)
    return evidence_root


def analyze(run_root: Path, protocol: dict[str, Any]) -> dict[str, Any]:
    cells = []
    for task in protocol["tasks"]:
        path = run_root / "raw" / clean._slug(protocol["base_model"]) / task / "terminal.json"
        row: dict[str, Any] = {"system": "FROGENT", "task": task, "status": "missing",
                               "score": None, "measured_cases": 0}
        if path.is_file():
            terminal = json.loads(path.read_text(encoding="utf-8"))
            row["status"] = terminal["status"]
            if terminal["status"] == "succeeded":
                details = scorer.SCORERS[task](terminal["response"])
                values = [float(item["score"]) for item in details
                          if isinstance(item.get("score"), (int, float))
                          and math.isfinite(float(item["score"]))]
                row.update(status="scored", score=sum(values) / len(values),
                           measured_cases=len(values))
            else:
                row["error"] = terminal.get("error", "")
        cells.append(row)
    complete = all(row["status"] == "scored" for row in cells)
    summary = {"schema_version": "frogent-sol-max-chemistry-mcp-analysis-v1",
               "status": "complete" if complete else "partial", "cells": cells,
               "claim_boundary": protocol["claim_boundary"]}
    output = run_root / "analysis"; output.mkdir(exist_ok=True)
    _write_json(output / "summary.json", summary)
    if complete:
        _write_json(output / "final-manifest.json", {
            "schema_version": "frogent-sol-max-chemistry-mcp-final-v1", "status": "complete",
            "model_id": protocol["base_model"], "reasoning_effort": protocol["reasoning_effort"],
            "scored_cells": len(cells), "claim_boundary": protocol["claim_boundary"],
        })
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--analyze-only", action="store_true")
    args = parser.parse_args()
    run_root = args.run_root.resolve(); run_root.relative_to(ROOT.resolve())
    protocol = _load_protocol(run_root)
    evidence_root = prepare_evidence(run_root, protocol)
    if args.prepare_only:
        return 0
    if not args.analyze_only:
        model = {"display_name": "FROGENT", "transport": "codex",
                 "model_id": protocol["base_model"],
                 "reasoning": {"effort": protocol["reasoning_effort"]}}
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(
                paired._run_cell, run_root, evidence_root, model, task,
                protocol["execution"]["batch_size"], 1, False, 12000, None, True, None,
            ) for task in protocol["tasks"]]
            for future in as_completed(futures):
                print(json.dumps(future.result(), ensure_ascii=False), flush=True)
    result = analyze(run_root, protocol)
    return 0 if result["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
