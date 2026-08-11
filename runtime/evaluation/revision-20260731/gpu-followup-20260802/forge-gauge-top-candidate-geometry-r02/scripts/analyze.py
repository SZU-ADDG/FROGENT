#!/usr/bin/env python3
"""Frozen top-candidate geometry analysis for the prospective Forge-Gauge panel."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from rdkit import Chem, RDLogger
from rdkit.Chem import QED
from repo.tools.sascorer import compute_sa_score


CONDITIONS = ("fixed_best", "single_pass", "iterative")
POCKETS = ("1IEP", "2HYY", "3CS9", "4WA9", "1M17")
SEEDS = (83, 97, 109)
TOP_K = 50


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=24)
    return parser.parse_args()


def canonical_smiles(mol: Chem.Mol) -> str:
    return Chem.MolToSmiles(Chem.RemoveHs(mol), canonical=True, isomericSmiles=True)


def heavy_coordinates(mol: Chem.Mol) -> np.ndarray:
    conf = mol.GetConformer()
    return np.asarray(
        [list(conf.GetAtomPosition(atom.GetIdx())) for atom in mol.GetAtoms() if atom.GetAtomicNum() > 1],
        dtype=float,
    )


def receptor_heavy_coordinates(path: Path) -> np.ndarray:
    coords: list[list[float]] = []
    for line in path.read_text(errors="replace").splitlines():
        if not line.startswith(("ATOM  ", "HETATM")):
            continue
        element = line[76:78].strip().upper()
        if not element:
            element = "".join(char for char in line[12:16] if char.isalpha()).upper()[:1]
        if element == "H":
            continue
        try:
            coords.append([float(line[30:38]), float(line[38:46]), float(line[46:54])])
        except ValueError:
            continue
    if not coords:
        raise ValueError(f"no receptor heavy atoms in {path}")
    return np.asarray(coords, dtype=float)


def read_single_sdf(path: Path) -> Chem.Mol | None:
    supplier = Chem.SDMolSupplier(str(path), sanitize=True, removeHs=False)
    return supplier[0] if supplier and len(supplier) else None


def prospective_seed(job: dict[str, Any]) -> int:
    seed = int(job["seed"])
    return seed - 10000 if job["stage"] == "round2" else seed


def scan_job(payload: tuple[dict[str, Any], str]) -> dict[str, Any]:
    job, source_text = payload
    source_root = Path(source_text)
    tag = job["tag"]
    job_root = source_root / "results" / tag
    sdf_paths = sorted(job_root.glob("sample_*.sdf"))
    csv_path = job_root / "generated_smiles_qed_sa.csv"
    if not csv_path.is_file():
        raise FileNotFoundError(csv_path)
    with csv_path.open(newline="") as handle:
        score_rows = list(csv.DictReader(handle))
    candidates: list[dict[str, Any]] = []
    parse_failures = 0
    seen: set[tuple[str, float, float]] = set()
    for sdf_path in sdf_paths:
        mol = read_single_sdf(sdf_path)
        if mol is None:
            parse_failures += 1
            continue
        qed = float(QED.qed(mol))
        favorable_sa = float(compute_sa_score(mol))
        identity = canonical_smiles(mol)
        dedup_key = (identity, round(qed, 12), round(favorable_sa, 12))
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        candidates.append(
            {
                "condition": job["condition"],
                "stage": job["stage"],
                "model": job["method"],
                "pocket": job["pocket"],
                "seed": prospective_seed(job),
                "job_tag": tag,
                "sample_file": sdf_path.name,
                "sample_path": str(sdf_path),
                "canonical_smiles": identity,
                "qed": qed,
                "favorable_sa": favorable_sa,
                "selection_score": 0.70 * qed + 0.30 * favorable_sa,
            }
        )
    if parse_failures:
        raise ValueError(f"{tag}: {parse_failures} generated SDF files failed RDKit parsing")
    candidates.sort(
        key=lambda item: (
            -item["selection_score"],
            -item["qed"],
            -item["favorable_sa"],
            item["job_tag"],
            item["sample_file"],
        )
    )
    return {
        "tag": tag,
        "condition": job["condition"],
        "stage": job["stage"],
        "model": job["method"],
        "pocket": job["pocket"],
        "seed": prospective_seed(job),
        "sdf_files": len(sdf_paths),
        "deduplicated_coordinate_candidates": len(candidates),
        "unlinked_property_csv_rows": len(score_rows),
        "top": candidates[:TOP_K],
    }


def finite_mean(values: Iterable[float | int | None]) -> float | None:
    selected = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return statistics.fmean(selected) if selected else None


def summarize(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[field] for field in fields)].append(row)
    output = []
    for key, items in sorted(groups.items()):
        record = dict(zip(fields, key))
        record.update(
            {
                "selected_molecules": len(items),
                "mean_selection_score": finite_mean(item["selection_score"] for item in items),
                "mean_qed": finite_mean(item["qed"] for item in items),
                "mean_favorable_sa": finite_mean(item["favorable_sa"] for item in items),
                "mean_pocket_atom_fraction": finite_mean(item["pocket_atom_fraction"] for item in items),
                "pocket_compatible_rate": finite_mean(float(item["pocket_compatible"]) for item in items),
                "severe_clash_free_rate": finite_mean(float(item["severe_clash_pairs"] == 0) for item in items),
                "mean_severe_clash_pairs": finite_mean(item["severe_clash_pairs"] for item in items),
                "mean_centroid_distance_angstrom": finite_mean(item["centroid_distance_angstrom"] for item in items),
                "model_counts": dict(sorted(Counter(item["model"] for item in items).items())),
            }
        )
        output.append(record)
    return output


def main() -> int:
    args = parse_args()
    source_root = args.source_root.resolve()
    input_root = args.input_root.resolve()
    protocol_path = args.protocol.resolve()
    output_root = args.output_root.resolve()
    if output_root.exists():
        raise FileExistsError(f"output root already exists: {output_root}")
    if not protocol_path.is_file():
        raise FileNotFoundError(protocol_path)
    protocol = json.loads(protocol_path.read_text())
    source_manifest_path = source_root / "final-manifest.json"
    source_manifest = json.loads(source_manifest_path.read_text())
    gate = protocol["source_gate"]
    for key in ("status", "expected_jobs", "exit_zero_jobs", "paired_cells_per_condition"):
        if source_manifest.get(key) != gate[key]:
            raise ValueError(f"source gate mismatch for {key}: {source_manifest.get(key)!r} != {gate[key]!r}")
    jobs = source_manifest.get("jobs", [])
    if len(jobs) != 120:
        raise ValueError(f"expected 120 jobs, found {len(jobs)}")
    observed_cells = {
        (job["condition"], job["pocket"], prospective_seed(job))
        for job in jobs
    }
    expected_cells = {(condition, pocket, seed) for condition in CONDITIONS for pocket in POCKETS for seed in SEEDS}
    if observed_cells != expected_cells:
        raise ValueError(f"cell mismatch: missing={sorted(expected_cells-observed_cells)} extra={sorted(observed_cells-expected_cells)}")

    RDLogger.DisableLog("rdApp.*")
    payloads = [(job, str(source_root)) for job in jobs]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        job_results = list(pool.map(scan_job, payloads))

    cell_candidates: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for result in job_results:
        cell_candidates[(result["condition"], result["pocket"], result["seed"])].extend(result["top"])

    references: dict[str, dict[str, np.ndarray]] = {}
    for pocket in POCKETS:
        ligand_path = input_root / pocket / "ligand-ph74.sdf"
        receptor_path = input_root / pocket / "receptor-selected.pdb"
        ligand = read_single_sdf(ligand_path)
        if ligand is None:
            raise ValueError(f"failed to parse reference ligand {ligand_path}")
        ligand_coords = heavy_coordinates(ligand)
        receptor_coords = receptor_heavy_coordinates(receptor_path)
        near_mask = np.min(np.linalg.norm(receptor_coords[:, None, :] - ligand_coords[None, :, :], axis=2), axis=1) <= 12.0
        references[pocket] = {
            "ligand_coords": ligand_coords,
            "centroid": ligand_coords.mean(axis=0),
            "receptor_coords": receptor_coords[near_mask],
        }

    selected_rows: list[dict[str, Any]] = []
    for cell in sorted(expected_cells):
        candidates = cell_candidates[cell]
        candidates.sort(
            key=lambda item: (
                -item["selection_score"],
                -item["qed"],
                -item["favorable_sa"],
                item["job_tag"],
                item["sample_file"],
            )
        )
        selected = candidates[:TOP_K]
        if len(selected) != TOP_K:
            raise ValueError(f"cell {cell} has only {len(selected)} selectable molecules")
        for rank, item in enumerate(selected, start=1):
            mol = read_single_sdf(Path(item["sample_path"]))
            if mol is None:
                raise ValueError(f"selected molecule became unreadable: {item['sample_path']}")
            coords = heavy_coordinates(mol)
            ref = references[item["pocket"]]
            ligand_distances = np.linalg.norm(coords[:, None, :] - ref["ligand_coords"][None, :, :], axis=2)
            receptor_distances = np.linalg.norm(coords[:, None, :] - ref["receptor_coords"][None, :, :], axis=2)
            pocket_fraction = float(np.mean(np.min(ligand_distances, axis=1) <= 10.0))
            item.update(
                {
                    "rank_in_cell": rank,
                    "pocket_atom_fraction": pocket_fraction,
                    "pocket_compatible": pocket_fraction == 1.0,
                    "centroid_distance_angstrom": float(np.linalg.norm(coords.mean(axis=0) - ref["centroid"])),
                    "severe_clash_pairs": int(np.sum(receptor_distances < 1.2)),
                }
            )
            selected_rows.append(item)

    if len(selected_rows) != 45 * TOP_K:
        raise ValueError(f"expected 2250 selected molecules, found {len(selected_rows)}")
    output_root.mkdir(parents=True)
    molecule_csv = output_root / "selected-molecule-geometry.csv"
    with molecule_csv.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(selected_rows[0]))
        writer.writeheader()
        writer.writerows(selected_rows)

    summary = {
        "schema_version": "frogent-forge-gauge-top-candidate-geometry-summary-v1",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "protocol_id": protocol["protocol_id"],
        "source_run": str(source_root),
        "source_manifest": str(source_manifest_path),
        "selected_molecules": len(selected_rows),
        "cells": 45,
        "top_k_per_cell": TOP_K,
        "source_generated_sdf_files": sum(result["sdf_files"] for result in job_results),
        "source_deduplicated_coordinate_candidates": sum(result["deduplicated_coordinate_candidates"] for result in job_results),
        "source_unlinked_property_csv_rows": sum(result["unlinked_property_csv_rows"] for result in job_results),
        "cell_summary": summarize(selected_rows, ("condition", "pocket", "seed")),
        "condition_summary": summarize(selected_rows, ("condition",)),
        "condition_model_summary": summarize(selected_rows, ("condition", "model")),
        "condition_pocket_summary": summarize(selected_rows, ("condition", "pocket")),
        "claim_limits": protocol["claim_limits"],
    }
    summary_path = output_root / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    final_manifest = {
        "status": "complete",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "protocol_id": protocol["protocol_id"],
        "source_protocol_id": source_manifest["protocol_id"],
        "source_expected_jobs": source_manifest["expected_jobs"],
        "source_exit_zero_jobs": source_manifest["exit_zero_jobs"],
        "expected_cells": 45,
        "completed_cells": len(summary["cell_summary"]),
        "top_k_per_cell": TOP_K,
        "selected_molecules": len(selected_rows),
        "summary": str(summary_path),
        "molecule_metrics": str(molecule_csv),
        "claim_boundary": "Coordinate-bearing top-50 QED/favorable-SA conditioned geometry and model-composition analysis, separate from unlinked source property-CSV top-50 sets; no binding-affinity claim.",
    }
    final_path = output_root / "final-manifest.json"
    final_path.write_text(json.dumps(final_manifest, indent=2, sort_keys=True) + "\n")
    print(final_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
