#!/usr/bin/env python3
"""Deterministically score the clean ten-model exposed eight-task panel."""

from __future__ import annotations

import argparse
import ast
import csv
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from rdkit import Chem, RDLogger, rdBase
from rdkit.Chem import QED
from rdkit.Contrib.SA_Score import sascorer

RDLogger.DisableLog("rdApp.error")


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_ROOT = (
    ROOT
    / "runtime/evaluation/revision-20260805/clean-ten-model-panel-budget-controlled-r03"
)
SOURCE_ROOT = (
    ROOT
    / "runtime/evaluation/revision-20260804/source-material/"
    "eight-task-benchmark-r01/extracted"
)


def _slug(model_id: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", model_id.casefold()).strip("-")


def _read_csv(name: str) -> list[dict[str, str]]:
    with (SOURCE_ROOT / name).open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _norm(value: str) -> str:
    return " ".join(value.casefold().strip().split())


def _norm_mc(value: str) -> str:
    labels = re.findall(r"[A-Z]", value.upper())
    return "/".join(sorted(dict.fromkeys(labels)))


def _canonical(smiles: str) -> str:
    molecule = Chem.MolFromSmiles(smiles.strip().strip("'\""))
    if molecule is None:
        raise ValueError(f"invalid SMILES: {smiles}")
    return Chem.MolToSmiles(molecule, isomericSmiles=True)


def _reaction(product: str, precursors: str) -> tuple[str, tuple[str, ...]]:
    return _canonical(product), tuple(sorted(_canonical(item) for item in precursors.split(".")))


def _reference_route(value: str) -> set[tuple[str, tuple[str, ...]]]:
    return {
        _reaction(product, precursors)
        for precursors, product in (step.split(" -> ", 1) for step in value.split(" | "))
    }


def _predicted_route(value: str) -> list[tuple[str, tuple[str, ...]]]:
    steps = []
    for encoded in value.split(" | "):
        precursors, product = encoded.split(" -> ", 1)
        steps.append(_reaction(product, precursors))
    return steps


def _f1(predicted: set[str], gold: set[str]) -> float:
    if not predicted and not gold:
        return 1.0
    if not predicted or not gold:
        return 0.0
    overlap = len(predicted & gold)
    precision = overlap / len(predicted)
    recall = overlap / len(gold)
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def _capped_relative(predicted: float, gold: float) -> float:
    if gold == 0:
        return float(predicted == 0)
    return max(1.0 - abs(predicted - gold) / abs(gold), 0.0)


def _by_index(response: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {int(item["case_index"]): item for item in response["results"]}


def _score_foundational(response: dict[str, Any]) -> list[dict[str, Any]]:
    source = _read_csv("test_data1.csv")
    predicted = _by_index(response)
    rows = []
    for row in source:
        index = int(row["index"])
        answer = str(predicted[index]["answer"])
        normalizer = _norm_mc if row["answer_type"] == "multipleChoice" else _norm
        correct = normalizer(answer) == normalizer(row["answer"])
        rows.append({"case_index": index, "score": float(correct), "correct": correct})
    return rows


def _score_drugs(response: dict[str, Any]) -> list[dict[str, Any]]:
    source = _read_csv("test_data2.csv")
    predicted = _by_index(response)
    rows = []
    for index, row in enumerate(source, 1):
        gold = {_norm(item) for item in row["answer"].split(";")}
        values = [_norm(item) for item in predicted[index]["drugbank_ids"][:5]]
        hits = len(gold & set(values))
        score = hits / min(5, len(gold))
        rows.append({
            "case_index": index,
            "score": score,
            "hits_at_5": hits,
            "returned_ids": len(values),
        })
    return rows


def _score_targets(response: dict[str, Any]) -> list[dict[str, Any]]:
    source = _read_csv("test_data3.csv")
    predicted = _by_index(response)
    rows = []
    for index, row in enumerate(source, 1):
        gold = {_norm(item) for item in row["answer"].split(";")}
        values = {_norm(item) for item in predicted[index]["targets"]}
        rows.append({"case_index": index, "score": _f1(values, gold),
                     "predicted_count": len(values), "gold_count": len(gold)})
    return rows


def _score_properties(response: dict[str, Any]) -> list[dict[str, Any]]:
    source = _read_csv("test_data4.csv")
    predicted = _by_index(response)
    rows = []
    for index, row in enumerate(source, 1):
        gold = row["answer"].split(";")
        item = predicted[index]
        endpoint_scores = {
            "qed": _capped_relative(float(item["qed"]), float(gold[0])),
            "caco2": _capped_relative(float(item["caco2"]), float(gold[1])),
            "bbbp": float(int(item["bbbp"]) == int(gold[2])),
            "cyp2d6_sub": float(int(item["cyp2d6_sub"]) == int(gold[3])),
            "sr_p53": float(int(item["sr_p53"]) == int(gold[4])),
        }
        rows.append({"case_index": index, "score": sum(endpoint_scores.values()) / 5,
                     "endpoint_scores": endpoint_scores})
    return rows


def _score_screening(response: dict[str, Any]) -> list[dict[str, Any]]:
    source = _read_csv("test_data5.csv")
    predicted = _by_index(response)
    rows = []
    for index, row in enumerate(source, 1):
        candidates = ast.literal_eval(row["smiles"])
        valid_source = row["answer"] in candidates
        selected = predicted[index]["selected_smiles"]
        rows.append({
            "case_index": index,
            "score": float(selected == row["answer"]) if valid_source else None,
            "correct": selected == row["answer"] if valid_source else None,
            "valid_source_case": valid_source,
        })
    return rows


def _score_mechanism(response: dict[str, Any]) -> list[dict[str, Any]]:
    source = _read_csv("test_data6.csv")
    predicted = _by_index(response)
    fields = [
        "hydrophobic_contacts",
        "hydrogen_bonds",
        "pi_stacking",
        "salt_bridges",
        "water_bridges",
    ]
    rows = []
    for index, row in enumerate(source, 1):
        gold = [int(item) for item in row["answer"].split(";")]
        exact = {field: int(predicted[index][field]) == gold[position]
                 for position, field in enumerate(fields)}
        rows.append({"case_index": index, "score": sum(exact.values()) / len(fields),
                     "field_exact": exact})
    return rows


def _score_design(response: dict[str, Any]) -> list[dict[str, Any]]:
    predicted = _by_index(response)
    rows = []
    for index in range(1, 21):
        canonical = []
        qeds = []
        easiness = []
        for smiles in predicted[index]["smiles"]:
            molecule = Chem.MolFromSmiles(smiles)
            if molecule is None:
                continue
            canonical.append(Chem.MolToSmiles(molecule, isomericSmiles=True))
            qeds.append(float(QED.qed(molecule)))
            sa = float(sascorer.calculateScore(molecule))
            easiness.append(min(max((10.0 - sa) / 9.0, 0.0), 1.0))
        validity = len(canonical) / 5
        uniqueness = len(set(canonical)) / 5
        mean_qed = sum(qeds) / len(qeds) if qeds else 0.0
        mean_easiness = sum(easiness) / len(easiness) if easiness else 0.0
        components = {
            "validity": validity,
            "uniqueness": uniqueness,
            "mean_qed": mean_qed,
            "mean_sa_easiness": mean_easiness,
        }
        rows.append({"case_index": index, "score": sum(components.values()) / 4,
                     "components": components})
    return rows


def _score_retro(response: dict[str, Any]) -> list[dict[str, Any]]:
    source = _read_csv("test_data8.csv")
    predicted = _by_index(response)
    rows = []
    for index, row in enumerate(source, 1):
        record: dict[str, Any] = {"case_index": index, "score": 0.0}
        try:
            target = _canonical(row["smiles"])
            reference = _reference_route(row["answer"])
            route = _predicted_route(predicted[index]["route"])
            route_set = set(route)
            target_rooted = bool(route) and route[0][0] == target
            recall = len(route_set & reference) / len(reference)
            record.update({
                "score": (float(target_rooted) + recall) / 2,
                "target_rooted": target_rooted,
                "reference_recall": recall,
                "parse_valid": True,
            })
        except Exception as exc:
            record.update({"target_rooted": False, "reference_recall": 0.0,
                           "parse_valid": False, "error": f"{type(exc).__name__}: {exc}"})
        rows.append(record)
    return rows


SCORERS = {
    "foundational_biomedical_knowledge": _score_foundational,
    "retrieve_known_drugs": _score_drugs,
    "retrieve_known_targets": _score_targets,
    "molecular_property_prediction": _score_properties,
    "virtual_screening": _score_screening,
    "binding_mechanism": _score_mechanism,
    "molecular_design": _score_design,
    "retrosynthesis_planning": _score_retro,
}


def _mean(values: list[float]) -> float | None:
    return None if not values else sum(values) / len(values)


def _observed_openrouter_usage(run_roots: list[Path]) -> dict[str, Any]:
    totals = {
        "response_files_with_usage": 0,
        "cost_usd": 0.0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "reasoning_tokens": 0,
    }
    for root in run_roots:
        for path in root.glob("raw/**/response.json"):
            try:
                usage = json.loads(path.read_text(encoding="utf-8")).get("usage")
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(usage, dict):
                continue
            totals["response_files_with_usage"] += 1
            totals["cost_usd"] += float(usage.get("cost") or 0.0)
            totals["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
            totals["completion_tokens"] += int(usage.get("completion_tokens") or 0)
            detail = usage.get("completion_tokens_details") or {}
            totals["reasoning_tokens"] += int(detail.get("reasoning_tokens") or 0)
    totals["cost_usd"] = round(totals["cost_usd"], 8)
    return totals


def _select_terminal(
    run_roots: list[Path], model_id: str, task: str
) -> tuple[Path | None, dict[str, Any] | None]:
    candidates: list[tuple[Path, dict[str, Any]]] = []
    for root in run_roots:
        path = root / "raw" / _slug(model_id) / task / "terminal.json"
        if path.exists():
            candidates.append((root, json.loads(path.read_text(encoding="utf-8"))))
    for root, terminal in candidates:
        if terminal.get("status") == "succeeded":
            return root, terminal
    return candidates[0] if candidates else (None, None)


def score(run_roots: list[Path]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    primary_root = run_roots[0]
    protocol = json.loads(
        (primary_root / "protocol/protocol.json").read_text(encoding="utf-8")
    )
    details: list[dict[str, Any]] = []
    cells: list[dict[str, Any]] = []
    for model in protocol["models"]:
        for task in protocol["tasks"]:
            source_root, terminal = _select_terminal(run_roots, model["model_id"], task)
            cell: dict[str, Any] = {
                "display_name": model["display_name"],
                "model_id": model["model_id"],
                "transport": model["transport"],
                "task": task,
                "status": "missing",
                "score": None,
            }
            if terminal is not None:
                cell["source_run"] = str(source_root.relative_to(ROOT))
                cell["status"] = terminal["status"]
                cell["wall_seconds"] = terminal.get("wall_seconds")
                metadata = terminal.get("transport_metadata") or {}
                cell["usage"] = metadata.get("usage")
                cell["provider"] = metadata.get("provider")
                cell["returned_model"] = metadata.get("returned_model")
                if terminal["status"] == "succeeded":
                    try:
                        scored = SCORERS[task](terminal["response"])
                        measured = [float(row["score"]) for row in scored
                                    if isinstance(row.get("score"), (int, float))
                                    and math.isfinite(float(row["score"]))]
                        cell["score"] = _mean(measured)
                        cell["measured_cases"] = len(measured)
                        cell["status"] = "scored"
                        for row in scored:
                            details.append({**cell, **row})
                    except Exception as exc:
                        cell["status"] = "scoring_failed"
                        cell["error"] = f"{type(exc).__name__}: {exc}"
                else:
                    cell["error"] = terminal.get("error")
            cells.append(cell)
    by_model: dict[str, list[float]] = defaultdict(list)
    for cell in cells:
        if isinstance(cell["score"], (int, float)):
            by_model[cell["model_id"]].append(float(cell["score"]))
    models = []
    for model in protocol["models"]:
        values = by_model[model["model_id"]]
        models.append({
            **model,
            "scored_tasks": len(values),
            "macro_mean": _mean(values) if len(values) == len(protocol["tasks"]) else None,
        })
    summary = {
        "schema_version": "frogent-clean-ten-model-score-v1",
        "status": "complete" if all(cell["status"] == "scored" for cell in cells)
        else "partial",
        "run_roots": [str(path.relative_to(ROOT)) for path in run_roots],
        "rdkit_version": rdBase.rdkitVersion,
        "openrouter_observed_usage_including_failed_calls": _observed_openrouter_usage(
            run_roots
        ),
        "cell_counts": {
            status: sum(cell["status"] == status for cell in cells)
            for status in sorted({cell["status"] for cell in cells})
        },
        "models": models,
        "cells": cells,
        "claim_boundary": (
            "Budget-controlled clean exposed-case comparison. Scores do not include FROGENT "
            "initialization, tool use, retrieval or persistent memory."
        ),
    }
    return details, summary


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-roots",
        nargs="+",
        type=Path,
        default=[DEFAULT_RUN_ROOT],
        help="Primary frozen run followed by ordered compatibility recovery roots",
    )
    parser.add_argument("--output-root", type=Path)
    parser.add_argument(
        "--finalize",
        action="store_true",
        help="Write final-manifest.json after every cell is scored or terminal-failed",
    )
    args = parser.parse_args()
    run_roots = [path.resolve() for path in args.run_roots]
    output_root = (args.output_root or (run_roots[0] / "analysis")).resolve()
    for path in (*run_roots, output_root):
        try:
            path.relative_to(ROOT)
        except ValueError as exc:
            raise ValueError("paths must stay inside the FROGENT project") from exc
    output_root.mkdir(parents=True, exist_ok=True)
    details, summary = score(run_roots)
    (output_root / "per-case.json").write_text(
        json.dumps(details, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_csv(
        output_root / "cells.csv",
        summary["cells"],
        ["display_name", "model_id", "transport", "task", "status", "score",
         "measured_cases", "wall_seconds", "provider", "returned_model", "source_run"],
    )
    _write_csv(
        output_root / "per-case.csv",
        details,
        ["display_name", "model_id", "transport", "task", "case_index", "score", "status"],
    )
    if args.finalize:
        unresolved = [
            cell for cell in summary["cells"]
            if cell["status"] in {"missing", "scoring_failed"}
        ]
        if unresolved:
            raise RuntimeError("cannot finalize while cells are missing or scoring failed")
        final_status = (
            "complete" if all(cell["status"] == "scored" for cell in summary["cells"])
            else "terminal_with_failures"
        )
        manifest = {
            "schema_version": "frogent-clean-ten-model-final-manifest-v1",
            "status": final_status,
            "cell_counts": summary["cell_counts"],
            "run_roots": summary["run_roots"],
            "openrouter_observed_usage_including_failed_calls":
                summary["openrouter_observed_usage_including_failed_calls"],
            "analysis_files": [
                "summary.json",
                "cells.csv",
                "per-case.json",
                "per-case.csv",
                "model-summary.csv",
                "figure/clean-ten-model-panel.png",
                "figure/clean-ten-model-panel.pdf",
                "figure/clean-ten-model-panel.svg"
            ],
            "claim_boundary": summary["claim_boundary"],
        }
        (output_root / "final-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(summary["cell_counts"], sort_keys=True))
    return 0 if summary["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
