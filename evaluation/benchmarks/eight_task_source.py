"""Validation for the submitted FROGENT eight-task benchmark source pack."""

from __future__ import annotations

import argparse
import ast
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


TASK_FILES = {
    "foundational_biomedical_knowledge": "test_data1.csv",
    "retrieve_known_drugs": "test_data2.csv",
    "retrieve_known_targets": "test_data3.csv",
    "molecular_property_prediction": "test_data4.csv",
    "virtual_screening": "test_data5.csv",
    "binding_mechanism": "test_data6.csv",
    "molecular_design": "test_data7_prompt.txt",
    "retrosynthesis_planning": "test_data8.csv",
}

EXPECTED_COLUMNS = {
    "test_data1.csv": [
        "index",
        "question",
        "answer",
        "answer_type",
        "rationale",
        "raw_subject",
    ],
    "test_data2.csv": ["question", "answer", "smiles"],
    "test_data3.csv": ["question", "answer"],
    "test_data4.csv": ["smiles", "question", "answer"],
    "test_data5.csv": ["smiles", "questions", "pdb_id", "answer"],
    "test_data6.csv": ["smiles", "protein", "question", "answer"],
    "test_data8.csv": ["smiles", "answer"],
}


class SourcePackError(ValueError):
    """Raised when a source pack violates the frozen input contract."""


def _read_csv(source_root: Path, name: str) -> list[dict[str, str]]:
    path = source_root / name
    if not path.is_file():
        raise SourcePackError(f"missing source file: {name}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        expected = EXPECTED_COLUMNS[name]
        if reader.fieldnames != expected:
            raise SourcePackError(
                f"{name} columns differ: expected {expected}, got {reader.fieldnames}"
            )
        rows = list(reader)
    if len(rows) != 20:
        raise SourcePackError(f"{name} must contain 20 cases, got {len(rows)}")
    blank_cells = [
        (row_index, column)
        for row_index, row in enumerate(rows, start=1)
        for column, value in row.items()
        if value is None or not value.strip()
    ]
    if blank_cells:
        raise SourcePackError(f"{name} has blank cells: {blank_cells[:5]}")
    return rows


def _pdb_stems(path: Path) -> set[str]:
    if not path.is_dir():
        raise SourcePackError(f"missing structure directory: {path.name}")
    return {entry.stem.lower() for entry in path.glob("*.pdb") if entry.is_file()}


def audit_source_pack(source_root: Path) -> dict[str, Any]:
    """Audit the frozen pack without exposing question or molecular payloads."""

    source_root = source_root.resolve(strict=True)
    rows = {
        index: _read_csv(source_root, f"test_data{index}.csv")
        for index in (1, 2, 3, 4, 5, 6, 8)
    }

    prompt_path = source_root / "test_data7_prompt.txt"
    if not prompt_path.is_file() or not prompt_path.read_text(encoding="utf-8").strip():
        raise SourcePackError("test_data7_prompt.txt is missing or blank")

    task5_candidates: list[list[str]] = []
    for row_index, row in enumerate(rows[5], start=1):
        try:
            candidates = ast.literal_eval(row["smiles"])
        except (SyntaxError, ValueError) as exc:
            raise SourcePackError(
                f"test_data5.csv row {row_index} has an invalid candidate list"
            ) from exc
        if not isinstance(candidates, list) or not all(
            isinstance(item, str) and item for item in candidates
        ):
            raise SourcePackError(
                f"test_data5.csv row {row_index} candidate list is malformed"
            )
        task5_candidates.append(candidates)

    invalid_virtual_screening = [
        {
            "row_index": row_index,
            "question_label": row["questions"],
            "pdb_id": row["pdb_id"],
            "candidate_count": len(candidates),
            "reason": "gold_not_in_candidate_pool",
        }
        for row_index, (row, candidates) in enumerate(
            zip(rows[5], task5_candidates, strict=True), start=1
        )
        if row["answer"] not in candidates
    ]

    pdb5 = _pdb_stems(source_root / "test_data5PDB")
    pdb6 = _pdb_stems(source_root / "test_data6PDB")
    pdb7_paths = sorted((source_root / "test_data7").glob("*.pdb"))
    required5 = {row["pdb_id"].lower() for row in rows[5]}
    required6 = {row["protein"].lower() for row in rows[6]}

    structure_checks = {
        "test_data5": {
            "required": len(required5),
            "available": len(pdb5),
            "missing": sorted(required5 - pdb5),
            "extra": sorted(pdb5 - required5),
        },
        "test_data6": {
            "required": len(required6),
            "available": len(pdb6),
            "missing": sorted(required6 - pdb6),
            "extra": sorted(pdb6 - required6),
        },
        "test_data7": {
            "required": 20,
            "available": len(pdb7_paths),
        },
    }
    if structure_checks["test_data5"]["missing"]:
        raise SourcePackError("test_data5PDB is missing referenced structures")
    if structure_checks["test_data6"]["missing"]:
        raise SourcePackError("test_data6PDB is missing referenced structures")
    if len(pdb7_paths) != 20:
        raise SourcePackError(
            f"test_data7 must contain 20 pocket structures, got {len(pdb7_paths)}"
        )

    task_summaries = {
        "foundational_biomedical_knowledge": {
            "cases": len(rows[1]),
            "answer_types": dict(Counter(row["answer_type"] for row in rows[1])),
            "subjects": dict(Counter(row["raw_subject"] for row in rows[1])),
        },
        "retrieve_known_drugs": {
            "cases": len(rows[2]),
            "gold_ids_per_case_min": min(len(row["answer"].split(";")) for row in rows[2]),
            "gold_ids_per_case_max": max(len(row["answer"].split(";")) for row in rows[2]),
        },
        "retrieve_known_targets": {
            "cases": len(rows[3]),
            "gold_targets_per_case": sorted(
                {len(row["answer"].split(";")) for row in rows[3]}
            ),
        },
        "molecular_property_prediction": {
            "cases": len(rows[4]),
            "endpoints_per_case": sorted(
                {len(row["question"].split(";")) for row in rows[4]}
            ),
        },
        "virtual_screening": {
            "attempted_cases": len(rows[5]),
            "valid_cases": len(rows[5]) - len(invalid_virtual_screening),
            "candidates_per_case": sorted({len(items) for items in task5_candidates}),
            "invalid_cases": invalid_virtual_screening,
        },
        "binding_mechanism": {
            "cases": len(rows[6]),
            "interaction_classes_per_case": sorted(
                {len(row["question"].split(";")) for row in rows[6]}
            ),
        },
        "molecular_design": {
            "cases": len(pdb7_paths),
            "prompt_present": True,
        },
        "retrosynthesis_planning": {
            "cases": len(rows[8]),
            "route_steps_min": min(row["answer"].count(" -> ") for row in rows[8]),
            "route_steps_max": max(row["answer"].count(" -> ") for row in rows[8]),
        },
    }

    return {
        "schema_version": "frogent-eight-task-source-audit-v1",
        "source_classification": "author-supplied_exposed_test_data",
        "task_files": TASK_FILES,
        "task_summaries": task_summaries,
        "structure_checks": structure_checks,
        "received_fields": {
            "case_inputs": True,
            "gold_or_reference_answers": True,
            "structure_inputs_for_tasks_5_6_7": True,
        },
        "missing_fields": {
            "original_model_outputs": True,
            "original_failure_rows": True,
            "original_random_seeds": True,
            "original_scorer_code": True,
            "task_versions_and_licenses": True,
            "judge_or_adjudication_records": True,
        },
        "primary_status": (
            "cases_and_gold_received_with_one_invalid_virtual_screening_case; "
            "headline_scores_not_yet_recomputable"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit_source_pack(args.source_root)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
