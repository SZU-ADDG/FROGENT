#!/usr/bin/env python3
"""Build combined RCSB PDB ligand and ChEMBL screening evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_clean_ten_model_panel as clean

DEFAULT_RUN_ROOT = ROOT / "runtime/evaluation/revision-20260811/frogent-sol-max-pdb-ligand-screening-r01"
CHEMBL_EVIDENCE = ROOT / "runtime/evaluation/revision-20260811/frogent-sol-max-chembl-screening-r01/evidence/virtual_screening.json"


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _call(pdb_id: str, candidates: list[str]) -> dict[str, Any]:
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
            "name": "rank_pdb_ligand_similarity",
            "arguments": {"pdb_id": pdb_id, "candidate_smiles": candidates},
        }},
    ]
    completed = subprocess.run(
        ["python3", "./scripts/launch_chemistry_mcp.py"],
        input="\n".join(json.dumps(row) for row in requests) + "\n",
        text=True, capture_output=True, cwd=ROOT, timeout=300, check=False,
    )
    rows = [json.loads(line) for line in completed.stdout.splitlines()]
    if completed.returncode or len(rows) != 2:
        raise RuntimeError(completed.stderr[-1000:])
    result = rows[1]["result"]
    if result.get("isError"):
        raise RuntimeError(result["content"][0]["text"])
    return result["structuredContent"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    run_root = args.run_root.resolve(); run_root.relative_to(ROOT.resolve())
    protocol = json.loads((run_root / "protocol/protocol.json").read_text())
    if protocol["status"] != "preregistered_before_full_pdb_ligand_outputs":
        raise ValueError("protocol is not preregistered")
    output = run_root / "evidence"
    if (output / "manifest.json").exists():
        return 0
    chembl = {
        int(row["case_index"]): row["target_active_similarity"]
        for row in json.loads(CHEMBL_EVIDENCE.read_text())
    }
    _, cases = clean._task_payload("virtual_screening")

    def execute(case: dict[str, Any]) -> dict[str, Any]:
        index = int(case["case_index"])
        path = output / "cases" / f"case-{index:02d}.json"
        if path.exists():
            return json.loads(path.read_text())
        record = {
            "case_index": index,
            "pdb_id": case["pdb_id"],
            "target": case["target"],
            "pdb_ligand_similarity": _call(case["pdb_id"], case["candidate_smiles"]),
            "target_active_similarity": chembl[index],
            "decision_policy": (
                "Prioritize an exact or near-exact PDB ligand match. Use target-active "
                "similarity only as supporting context; neither signal is affinity."
            ),
        }
        _write(path, record)
        return record

    failures = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(execute, case): int(case["case_index"]) for case in cases}
        for future in as_completed(futures):
            index = futures[future]
            try:
                record = future.result()
                pdb = record["pdb_ligand_similarity"]
                print(json.dumps({"case_index": index, "status": pdb["status"],
                                  "ligands": len(pdb["ligands"])}), flush=True)
            except Exception as error:
                failures.append({"case_index": index,
                                 "error": f"{type(error).__name__}: {error}"})
                print(json.dumps(failures[-1]), flush=True)
    paths = sorted((output / "cases").glob("case-*.json"))
    if failures or len(paths) != 20:
        _write(output / "status.json", {"status": "partial", "failures": failures,
                                         "completed_cases": len(paths)})
        return 2
    records = [json.loads(path.read_text()) for path in paths]
    _write(output / "virtual_screening.json", records)
    _write(output / "manifest.json", {
        "schema_version": "frogent-pdb-ligand-screening-evidence-v1",
        "status": "complete", "gold_visibility": "withheld", "cases": 20,
        "resolved_pdb_ligand_cases": sum(
            row["pdb_ligand_similarity"]["status"] == "resolved" for row in records
        ),
        "mcp_tools": ["chemistry.rank_pdb_ligand_similarity",
                      "chemistry.rank_target_active_similarity"],
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
