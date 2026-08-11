#!/usr/bin/env python3
"""Run the preregistered chemistry MCP canary through stdio."""

from __future__ import annotations

import json
import math
import subprocess
import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_ROOT = ROOT / "runtime/evaluation/revision-20260811/chemistry-mcp-canary-r02"


def _request(identifier: int, method: str, params: dict) -> dict:
    return {"jsonrpc": "2.0", "id": identifier, "method": method, "params": params}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    args = parser.parse_args()
    run_root = args.run_root.resolve()
    run_root.relative_to(ROOT.resolve())
    protocol = json.loads(
        (run_root / "protocol/protocol.json").read_text(encoding="utf-8")
    )
    if protocol.get("status") != "preregistered_before_outputs":
        raise ValueError("chemistry canary protocol is not preregistered")
    cases = protocol["cases"]
    requests = (
        _request(1, "initialize", {}),
        _request(2, "tools/call", {
            "name": "describe_molecules",
            "arguments": {"smiles": cases["descriptor_smiles"]},
        }),
        _request(3, "tools/call", {
            "name": "rank_molecular_similarity",
            "arguments": {
                "query_smiles": cases["similarity_query"],
                "candidate_smiles": cases["similarity_candidates"],
            },
        }),
    )
    completed = subprocess.run(
        ["python3", "./scripts/launch_chemistry_mcp.py"],
        input="\n".join(json.dumps(item) for item in requests) + "\n",
        text=True,
        capture_output=True,
        cwd=ROOT,
        check=False,
    )
    responses = [json.loads(line) for line in completed.stdout.splitlines()]
    errors = []
    if completed.returncode != 0:
        errors.append(f"server exit code {completed.returncode}")
    if len(responses) != 3 or any("error" in response for response in responses):
        errors.append("MCP protocol response failure")
    descriptor_results = (
        responses[1].get("result", {}).get("structuredContent", {}).get("results", [])
        if len(responses) > 1 else []
    )
    similarity_results = (
        responses[2].get("result", {}).get("structuredContent", {}).get("results", [])
        if len(responses) > 2 else []
    )
    if len(descriptor_results) != 2:
        errors.append("descriptor result count mismatch")
    if len(similarity_results) != 4:
        errors.append("similarity result count mismatch")
    if not similarity_results or similarity_results[0].get("tanimoto") != 1.0:
        errors.append("identical structure did not rank first at Tanimoto 1.0")
    numeric = [
        value
        for result in descriptor_results
        for key, value in result.items()
        if key in {"molecular_weight", "exact_mass", "clogp", "tpsa", "fraction_csp3", "qed"}
    ] + [result.get("tanimoto") for result in similarity_results]
    if any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in numeric):
        errors.append("non-finite numeric output")
    analysis = {
        "schema_version": "frogent-chemistry-mcp-canary-analysis-v1",
        "status": "complete" if not errors else "failed",
        "errors": errors,
        "server_returncode": completed.returncode,
        "responses": responses,
        "stderr": completed.stderr,
        "claim_boundary": protocol["claim_boundary"],
    }
    output = run_root / "analysis"
    output.mkdir(exist_ok=True)
    (output / "result.json").write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not errors:
        (output / "final-manifest.json").write_text(
            json.dumps({
                "schema_version": "frogent-chemistry-mcp-canary-final-v1",
                "status": "complete",
                "tools_verified": protocol["tools"],
                "analysis_files": ["result.json"],
                "claim_boundary": protocol["claim_boundary"],
            }, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({"status": analysis["status"], "errors": errors}))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
