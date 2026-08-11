#!/usr/bin/env python3
"""Build gold-blind target-active similarity evidence for screening cases."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.molecular.chembl_evidence import BASE_URL, fetch_json
from scripts import run_clean_ten_model_panel as clean

DEFAULT_RUN_ROOT = ROOT / "runtime/evaluation/revision-20260811/frogent-sol-max-chembl-screening-r01"


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _call_mcp(target: str, candidate_smiles: list[str]) -> dict[str, Any]:
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "rank_target_active_similarity",
                "arguments": {
                    "target": target,
                    "candidate_smiles": candidate_smiles,
                    "max_unique_actives": 1000,
                    "min_pchembl": 6.0,
                },
            },
        },
    ]
    completed = subprocess.run(
        ["python3", "./scripts/launch_chemistry_mcp.py"],
        input="\n".join(json.dumps(row) for row in requests) + "\n",
        text=True,
        capture_output=True,
        cwd=ROOT,
        timeout=900,
        check=False,
    )
    responses = [json.loads(line) for line in completed.stdout.splitlines()]
    if completed.returncode or len(responses) != 2:
        raise RuntimeError(
            f"chemistry MCP transport failed ({completed.returncode}): "
            f"{completed.stderr[-1200:]}"
        )
    result = responses[1].get("result") or {}
    if result.get("isError"):
        message = (result.get("content") or [{"text": "unknown error"}])[0]["text"]
        raise RuntimeError(message)
    return result["structuredContent"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    run_root = args.run_root.resolve()
    run_root.relative_to(ROOT.resolve())
    protocol_path = run_root / "protocol/protocol.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("status") != "preregistered_before_target_active_outputs":
        raise ValueError("target-active evidence requires a preregistered protocol")
    output = run_root / "evidence"
    manifest_path = output / "manifest.json"
    if manifest_path.exists():
        print(manifest_path)
        return 0
    _, cases = clean._task_payload("virtual_screening")

    def execute(case: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        index = int(case["case_index"])
        path = output / "cases" / f"case-{index:02d}.json"
        if path.exists():
            return index, json.loads(path.read_text(encoding="utf-8"))
        evidence = _call_mcp(str(case["target"]), list(case["candidate_smiles"]))
        record = {
            "case_index": index,
            "target": case["target"],
            "pdb_id": case["pdb_id"],
            "target_active_similarity": evidence,
        }
        _write_json(path, record)
        return index, record

    failures: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(execute, case): int(case["case_index"]) for case in cases}
        for future in as_completed(futures):
            index = futures[future]
            try:
                _, record = future.result()
                print(json.dumps({
                    "case_index": index,
                    "target_chembl_id": record["target_active_similarity"]["target"][
                        "target_chembl_id"
                    ],
                    "unique_known_actives": record["target_active_similarity"][
                        "active_collection"
                    ]["unique_known_actives"],
                }), flush=True)
            except Exception as error:
                failures.append({
                    "case_index": index,
                    "error": f"{type(error).__name__}: {error}",
                })
                print(json.dumps(failures[-1]), flush=True)
    case_paths = sorted((output / "cases").glob("case-*.json"))
    status = fetch_json(f"{BASE_URL}/status.json")
    _write_json(output / "chembl-status.json", status)
    summary = {
        "schema_version": "frogent-chembl-screening-evidence-status-v1",
        "status": "complete" if len(case_paths) == len(cases) and not failures else "partial",
        "expected_cases": len(cases),
        "completed_cases": len(case_paths),
        "failed_cases": failures,
    }
    _write_json(output / "status.json", summary)
    if summary["status"] != "complete":
        return 2
    records = [json.loads(path.read_text(encoding="utf-8")) for path in case_paths]
    _write_json(output / "virtual_screening.json", records)
    _write_json(manifest_path, {
        "schema_version": "frogent-chembl-screening-evidence-manifest-v1",
        "status": "complete",
        "gold_visibility": "withheld",
        "mcp_tool": "chemistry.rank_target_active_similarity",
        "cases": len(records),
        "protocol_sha256": _sha256(protocol_path),
        "evidence_sha256": _sha256(output / "virtual_screening.json"),
        "chembl_status_sha256": _sha256(output / "chembl-status.json"),
        "resolved_target_chembl_ids": [
            row["target_active_similarity"]["target"]["target_chembl_id"]
            for row in records
        ],
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
