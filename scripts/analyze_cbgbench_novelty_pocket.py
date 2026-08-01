#!/usr/bin/env python3
"""Analyze CBGBench primary molecules for identity, scaffold and pocket geometry."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from rdkit import Chem, DataStructs, RDLogger
from rdkit.Chem import AllChem
from rdkit.Chem.Scaffolds import MurckoScaffold


TAG_RE = re.compile(
    r"^(?P<model>targetdiff|diffsbdd|pocket2mol)-(?P<pocket>[a-z0-9]+)-s(?P<seed>\d+)-n500-a01$"
)
POCKETS = ("1IEP", "2HYY", "3CS9", "4WA9", "1M17")
MODELS = ("targetdiff", "diffsbdd", "pocket2mol")
SEEDS = (17, 23, 31)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    return parser.parse_args()


def load_single_sdf(path: Path, sanitize: bool = True) -> Chem.Mol | None:
    supplier = Chem.SDMolSupplier(str(path), sanitize=sanitize, removeHs=False)
    return supplier[0] if supplier and len(supplier) else None


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
            element = re.sub(r"[^A-Za-z]", "", line[12:16]).upper()[:1]
        if element == "H":
            continue
        try:
            coords.append([float(line[30:38]), float(line[38:46]), float(line[46:54])])
        except ValueError:
            continue
    if not coords:
        raise ValueError(f"no receptor heavy-atom coordinates in {path}")
    return np.asarray(coords, dtype=float)


def canonical_identity(mol: Chem.Mol) -> str:
    return Chem.MolToSmiles(Chem.RemoveHs(mol), canonical=True, isomericSmiles=True)


def scaffold_smiles(mol: Chem.Mol) -> str:
    scaffold = MurckoScaffold.GetScaffoldForMol(Chem.RemoveHs(mol))
    return Chem.MolToSmiles(scaffold, canonical=True, isomericSmiles=False) if scaffold.GetNumAtoms() else ""


def fingerprint(mol: Chem.Mol):
    return AllChem.GetMorganFingerprintAsBitVect(Chem.RemoveHs(mol), 2, nBits=2048)


def finite_mean(values: Iterable[float]) -> float | None:
    vals = [v for v in values if isinstance(v, (int, float)) and math.isfinite(v)]
    return statistics.fmean(vals) if vals else None


def finite_median(values: Iterable[float]) -> float | None:
    vals = [v for v in values if isinstance(v, (int, float)) and math.isfinite(v)]
    return statistics.median(vals) if vals else None


def aggregate(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row[field] for field in fields)].append(row)
    output: list[dict[str, Any]] = []
    for key, items in sorted(grouped.items()):
        valid = [item for item in items if item["parse_success"]]
        identities = {item["canonical_smiles"] for item in valid}
        scaffolds = {item["scaffold_smiles"] for item in valid if item["scaffold_smiles"]}
        record = dict(zip(fields, key))
        record.update(
            {
                "files": len(items),
                "parse_success": len(valid),
                "parse_success_rate": len(valid) / len(items) if items else None,
                "unique_identities": len(identities),
                "identity_uniqueness": len(identities) / len(valid) if valid else None,
                "unique_scaffolds": len(scaffolds),
                "scaffold_per_molecule": len(scaffolds) / len(valid) if valid else None,
                "mean_reference_tanimoto": finite_mean(item["reference_tanimoto"] for item in valid),
                "median_reference_tanimoto": finite_median(item["reference_tanimoto"] for item in valid),
                "reference_tanimoto_ge_0_5_rate": finite_mean(float(item["reference_tanimoto"] >= 0.5) for item in valid),
                "reference_identity_match_rate": finite_mean(float(item["reference_identity_match"]) for item in valid),
                "reference_scaffold_match_rate": finite_mean(float(item["reference_scaffold_match"]) for item in valid),
                "mean_pocket_atom_fraction": finite_mean(item["pocket_atom_fraction"] for item in valid),
                "pocket_compatible_rate": finite_mean(float(item["pocket_compatible"]) for item in valid),
                "severe_clash_free_rate": finite_mean(float(item["severe_clash_pairs"] == 0) for item in valid),
                "mean_centroid_distance_angstrom": finite_mean(item["centroid_distance_angstrom"] for item in valid),
            }
        )
        output.append(record)
    return output


def main() -> int:
    args = parse_args()
    input_root = args.input_root.resolve()
    output_root = args.output_root.resolve()
    protocol = args.protocol.resolve()
    if output_root.exists():
        raise FileExistsError(f"output root already exists: {output_root}")
    if input_root == output_root or input_root in output_root.parents:
        raise ValueError("output root must be isolated from the input run")
    if not protocol.is_file():
        raise FileNotFoundError(protocol)
    primary_manifest = input_root / "final-manifest.json"
    manifest_data = json.loads(primary_manifest.read_text())
    if manifest_data.get("expected_jobs") != 45 or manifest_data.get("exit_zero_jobs") != 45:
        raise ValueError("primary manifest is not a validated 45/45 terminal-success matrix")

    output_root.mkdir(parents=True)
    RDLogger.DisableLog("rdApp.*")
    references: dict[str, dict[str, Any]] = {}
    for pocket in POCKETS:
        ligand_path = input_root / "inputs" / pocket / "ligand-ph74.sdf"
        receptor_path = input_root / "inputs" / pocket / "receptor-selected.pdb"
        ligand = load_single_sdf(ligand_path)
        if ligand is None:
            raise ValueError(f"failed to parse reference ligand: {ligand_path}")
        ligand_coords = heavy_coordinates(ligand)
        receptor_coords = receptor_heavy_coordinates(receptor_path)
        near_mask = np.min(np.linalg.norm(receptor_coords[:, None, :] - ligand_coords[None, :, :], axis=2), axis=1) <= 12.0
        references[pocket] = {
            "mol": ligand,
            "identity": canonical_identity(ligand),
            "scaffold": scaffold_smiles(ligand),
            "fingerprint": fingerprint(ligand),
            "coords": ligand_coords,
            "centroid": ligand_coords.mean(axis=0),
            "receptor_coords": receptor_coords[near_mask],
        }

    full_root = input_root / "results" / "full"
    job_dirs = []
    for path in sorted(full_root.iterdir()):
        match = TAG_RE.match(path.name)
        if match:
            job_dirs.append((path, match.groupdict()))
    expected = {(m, p.lower(), str(s)) for m in MODELS for p in POCKETS for s in SEEDS}
    observed = {(meta["model"], meta["pocket"], meta["seed"]) for _, meta in job_dirs}
    if observed != expected:
        raise ValueError(f"primary job set mismatch: missing={sorted(expected-observed)} extra={sorted(observed-expected)}")

    rows: list[dict[str, Any]] = []
    for job_dir, meta in job_dirs:
        pocket = meta["pocket"].upper()
        ref = references[pocket]
        for sdf_path in sorted(job_dir.glob("sample_*.sdf")):
            row: dict[str, Any] = {
                "model": meta["model"],
                "pocket": pocket,
                "seed": int(meta["seed"]),
                "job_tag": job_dir.name,
                "sample_file": sdf_path.name,
                "parse_success": False,
                "canonical_smiles": "",
                "scaffold_smiles": "",
                "reference_tanimoto": None,
                "reference_identity_match": False,
                "reference_scaffold_match": False,
                "pocket_atom_fraction": None,
                "pocket_compatible": False,
                "centroid_distance_angstrom": None,
                "severe_clash_pairs": None,
                "error": "",
            }
            try:
                mol = load_single_sdf(sdf_path)
                if mol is None:
                    raise ValueError("RDKit parse returned no molecule")
                coords = heavy_coordinates(mol)
                if not len(coords):
                    raise ValueError("molecule has no heavy-atom coordinates")
                identity = canonical_identity(mol)
                scaffold = scaffold_smiles(mol)
                ligand_distances = np.linalg.norm(coords[:, None, :] - ref["coords"][None, :, :], axis=2)
                receptor_distances = np.linalg.norm(
                    coords[:, None, :] - ref["receptor_coords"][None, :, :], axis=2
                )
                pocket_fraction = float(np.mean(np.min(ligand_distances, axis=1) <= 10.0))
                row.update(
                    {
                        "parse_success": True,
                        "canonical_smiles": identity,
                        "scaffold_smiles": scaffold,
                        "reference_tanimoto": float(DataStructs.TanimotoSimilarity(fingerprint(mol), ref["fingerprint"])),
                        "reference_identity_match": identity == ref["identity"],
                        "reference_scaffold_match": bool(scaffold) and scaffold == ref["scaffold"],
                        "pocket_atom_fraction": pocket_fraction,
                        "pocket_compatible": pocket_fraction == 1.0,
                        "centroid_distance_angstrom": float(np.linalg.norm(coords.mean(axis=0) - ref["centroid"])),
                        "severe_clash_pairs": int(np.sum(receptor_distances < 1.2)),
                    }
                )
            except Exception as exc:
                row["error"] = f"{type(exc).__name__}: {exc}"
            rows.append(row)

    if not rows:
        raise ValueError("no primary SDF files discovered")
    molecule_csv = output_root / "molecule-metrics.csv"
    with molecule_csv.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    job_summary = aggregate(rows, ("model", "pocket", "seed", "job_tag"))
    model_pocket_summary = aggregate(rows, ("model", "pocket"))
    model_summary = aggregate(rows, ("model",))
    summary = {
        "schema_version": "frogent-cbgbench-novelty-pocket-summary-v1",
        "created_at": datetime.now().astimezone().isoformat(),
        "input_run": str(input_root),
        "output_run": str(output_root),
        "protocol": str(protocol),
        "primary_manifest": str(primary_manifest),
        "files": len(rows),
        "parse_success": sum(bool(row["parse_success"]) for row in rows),
        "parse_failures": sum(not bool(row["parse_success"]) for row in rows),
        "job_summary": job_summary,
        "model_pocket_summary": model_pocket_summary,
        "model_summary": model_summary,
        "claim_limits": json.loads(protocol.read_text())["claim_limits"],
    }
    summary_path = output_root / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    final_manifest = {
        "schema_version": "frogent-cbgbench-novelty-pocket-manifest-v1",
        "created_at": datetime.now().astimezone().isoformat(),
        "status": "complete" if summary["parse_failures"] == 0 else "complete_with_parse_failures",
        "input_run": str(input_root),
        "output_run": str(output_root),
        "jobs_analyzed": len(job_summary),
        "molecule_files": len(rows),
        "parse_success": summary["parse_success"],
        "parse_failures": summary["parse_failures"],
        "outputs": [str(molecule_csv), str(summary_path)],
    }
    (output_root / "final-manifest.json").write_text(json.dumps(final_manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(final_manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
