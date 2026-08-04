#!/usr/bin/env python3
"""Score exposed DirectMultiStep routes against canonicalized reference reactions."""

from __future__ import annotations

import argparse
import ast
import csv
import json
import math
from pathlib import Path
from typing import Any

from rdkit import Chem, rdBase


def _canonical(smiles: str) -> str:
    molecule = Chem.MolFromSmiles(smiles.strip().strip("'\""))
    if molecule is None:
        raise ValueError(f"invalid SMILES: {smiles}")
    return Chem.MolToSmiles(molecule, isomericSmiles=True)


def _reaction(product: str, precursors: str) -> tuple[str, tuple[str, ...]]:
    return _canonical(product), tuple(sorted(_canonical(item) for item in precursors.split(".")))


def parse_reference_route(value: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    reactions = []
    for step in value.split(" | "):
        precursors, product = step.split(" -> ", 1)
        reactions.append(_reaction(product, precursors))
    return tuple(reactions)


def _sse_payload(value: str) -> dict[str, Any]:
    for line in value.splitlines():
        if line.startswith("data: "):
            payload = json.loads(line[6:])
            if "result" in payload or "error" in payload:
                return payload
    raise ValueError("SSE response has no JSON-RPC result")


def parse_predicted_routes(value: str) -> tuple[tuple[tuple[str, tuple[str, ...]], ...], ...]:
    payload = _sse_payload(value)
    if "error" in payload:
        raise ValueError("JSON-RPC returned an error")
    result = payload["result"]
    if result.get("isError"):
        raise ValueError("MCP tool returned isError")
    content = result.get("content") or []
    text = next(item["text"] for item in content if item.get("type") == "text")
    route_map = json.loads(text)
    routes = []
    for key in sorted(route_map, key=lambda item: int(item.rsplit(" ", 1)[-1])):
        encoded = route_map[key].strip().strip("`")
        steps = ast.literal_eval(encoded)
        reactions = []
        for step in steps:
            product, precursors = step.split("->", 1)
            reactions.append(_reaction(product, precursors))
        routes.append(tuple(reactions))
    return tuple(routes)


def _route_metrics(
    target: str,
    reference: tuple[tuple[str, tuple[str, ...]], ...],
    routes: tuple[tuple[tuple[str, tuple[str, ...]], ...], ...],
) -> dict[str, Any]:
    target_canonical = _canonical(target)
    reference_set = set(reference)
    per_route = []
    for route in routes:
        route_set = set(route)
        overlap = len(route_set & reference_set)
        per_route.append({
            "full_exact": route_set == reference_set,
            "reference_recall": overlap / len(reference_set),
            "precision": overlap / len(route_set) if route_set else 0.0,
            "target_rooted": bool(route) and route[0][0] == target_canonical,
            "steps": len(route),
        })
    top5 = per_route[:5]
    return {
        "route_count": len(routes),
        "nonempty": bool(routes),
        "top1_full_exact": bool(per_route) and per_route[0]["full_exact"],
        "top5_full_exact": any(item["full_exact"] for item in top5),
        "top1_target_rooted": bool(per_route) and per_route[0]["target_rooted"],
        "top5_best_reference_recall": max((item["reference_recall"] for item in top5), default=0.0),
        "top5_best_precision": max((item["precision"] for item in top5), default=0.0),
        "reference_steps": len(reference),
    }


def analyze(source_csv: Path, raw_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    with source_csv.open(newline="", encoding="utf-8-sig") as handle:
        source = list(csv.DictReader(handle))
    details = []
    for case_index, row in enumerate(source, start=1):
        reference = parse_reference_route(row["answer"])
        for tool in ("generate_routes_flash", "generate_routes_explorer"):
            path = raw_root / f"case-{case_index:02d}" / f"{tool}.sse"
            record: dict[str, Any] = {"case_index": case_index, "tool": tool, "status": "failed"}
            try:
                routes = parse_predicted_routes(path.read_text(encoding="utf-8"))
                record.update(_route_metrics(row["smiles"], reference, routes))
                record["status"] = "scored"
            except Exception as exc:
                record["error"] = f"{type(exc).__name__}: {exc}"
            details.append(record)

    by_tool = {}
    for tool in ("generate_routes_flash", "generate_routes_explorer"):
        rows = [item for item in details if item["tool"] == tool]
        scored = [item for item in rows if item["status"] == "scored"]
        by_tool[tool] = {
            "attempted_cases": len(rows),
            "scored_cases": len(scored),
            "failed_cases": len(rows) - len(scored),
            "nonempty_rate": sum(item["nonempty"] for item in scored) / len(rows),
            "top1_target_rooted_rate": sum(item["top1_target_rooted"] for item in scored) / len(rows),
            "top1_full_exact_rate": sum(item["top1_full_exact"] for item in scored) / len(rows),
            "top5_full_exact_rate": sum(item["top5_full_exact"] for item in scored) / len(rows),
            "mean_top5_best_reference_recall": sum(item["top5_best_reference_recall"] for item in scored) / len(rows),
            "mean_top5_best_precision": sum(item["top5_best_precision"] for item in scored) / len(rows),
        }
    return details, {
        "schema_version": "frogent-eight-task-retrosynthesis-exposed-result-v1",
        "status": "complete" if all(row["status"] == "scored" for row in details) else "complete_with_failures",
        "source_classification": "author-supplied_exposed_test_data",
        "rdkit_version": rdBase.rdkitVersion,
        "tools": by_tool,
        "claim_boundary": (
            "Post-hoc exposed-case deterministic exact-route audit. Alternative chemically valid "
            "routes require separate blinded semantic adjudication."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_csv", type=Path)
    parser.add_argument("raw_root", type=Path)
    parser.add_argument("output_root", type=Path)
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=False)
    details, summary = analyze(args.source_csv, args.raw_root)
    (args.output_root / "per-case.json").write_text(
        json.dumps(details, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output_root / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
