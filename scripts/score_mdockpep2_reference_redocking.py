#!/usr/bin/env python3
"""Score MDockPeP2 peptide poses against native peptide CA coordinates."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_ROOT = ROOT / (
    "runtime/evaluation/revision-20260807/mdockpep2-reference-redocking-r01"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ca_models(path: Path) -> list[dict[str, Any]]:
    models: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    implicit = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("MODEL"):
            if current is not None:
                models.append(current)
            parts = line.split()
            current = {"model_index": int(parts[-1]), "ca": [], "remarks": {}}
            implicit = False
            continue
        if current is None and line.startswith(("ATOM", "HETATM")):
            current = {"model_index": 1, "ca": [], "remarks": {}}
            implicit = True
        if current is None:
            continue
        if line.startswith("REMARK") and ":" in line:
            label, value = line[6:].split(":", 1)
            try:
                current["remarks"][label.strip()] = float(value.strip())
            except ValueError:
                current["remarks"][label.strip()] = value.strip()
        if line.startswith(("ATOM", "HETATM")) and line[12:16].strip() == "CA":
            current["ca"].append(
                {
                    "resname": line[17:20].strip(),
                    "resseq": int(line[22:26]),
                    "coord": [float(line[30:38]), float(line[38:46]), float(line[46:54])],
                }
            )
        if line.startswith("ENDMDL"):
            models.append(current)
            current = None
            implicit = False
    if current is not None:
        models.append(current)
    if not models:
        raise ValueError(f"no coordinate models found in {path}")
    if any(not model["ca"] for model in models):
        raise ValueError(f"one or more models contain no CA atoms in {path}")
    return models


def _kabsch_rmsd(mobile: np.ndarray, target: np.ndarray) -> float:
    mobile_centered = mobile - mobile.mean(axis=0)
    target_centered = target - target.mean(axis=0)
    covariance = mobile_centered.T @ target_centered
    left, _, right = np.linalg.svd(covariance)
    correction = np.eye(3)
    correction[-1, -1] = np.sign(np.linalg.det(left @ right))
    rotation = left @ correction @ right
    aligned = mobile_centered @ rotation
    return float(np.sqrt(np.mean(np.sum((aligned - target_centered) ** 2, axis=1))))


def _score_models(native_path: Path, predicted_path: Path) -> list[dict[str, Any]]:
    native_models = _ca_models(native_path)
    if len(native_models) != 1:
        raise ValueError(f"native peptide must contain exactly one model: {native_path}")
    native = native_models[0]["ca"]
    scored = []
    for model in _ca_models(predicted_path):
        predicted = model["ca"]
        if len(predicted) != len(native):
            raise ValueError(
                f"CA count mismatch for model {model['model_index']}: "
                f"predicted={len(predicted)} native={len(native)}"
            )
        predicted_array = np.asarray([atom["coord"] for atom in predicted], dtype=float)
        native_array = np.asarray([atom["coord"] for atom in native], dtype=float)
        direct = float(
            np.sqrt(np.mean(np.sum((predicted_array - native_array) ** 2, axis=1)))
        )
        scored.append(
            {
                "model_index": model["model_index"],
                "ca_atoms": len(native),
                "receptor_frame_ca_rmsd_angstrom": direct,
                "superposed_ca_rmsd_angstrom": _kabsch_rmsd(predicted_array, native_array),
                "predicted_residue_names": [atom["resname"] for atom in predicted],
                "native_residue_names": [atom["resname"] for atom in native],
                "remarks": model["remarks"],
            }
        )
    return scored


def _parse_runtime(path: Path) -> float:
    match = re.search(r"[-+]?\d+(?:\.\d+)?", path.read_text(encoding="utf-8"))
    if not match:
        raise ValueError(f"no runtime value found in {path}")
    return float(match.group(0))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    args = parser.parse_args()
    run_root = args.run_root.resolve()
    run_root.relative_to(ROOT)
    protocol = json.loads((run_root / "protocol/protocol.json").read_text(encoding="utf-8"))
    cases = []
    for case in protocol["cases"]:
        case_id = case["case_id"]
        case_root = run_root / "jobs" / case_id
        exit_code = int((case_root / "state/exit-code").read_text(encoding="utf-8").strip())
        predicted_path = case_root / "output/mdockpep2_out.pdb"
        scores_path = case_root / "output/Sampling_scores_all.txt"
        runtime_path = case_root / "output/running_time.txt"
        native_path = run_root / "inputs" / f"{case_id}-native-peptide.pdb"
        if exit_code != 0:
            raise RuntimeError(f"{case_id} exited {exit_code}")
        for required in (predicted_path, scores_path, runtime_path, native_path):
            if not required.is_file() or required.stat().st_size == 0:
                raise FileNotFoundError(required)
        models = _score_models(native_path, predicted_path)
        score_lines = [line for line in scores_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        cases.append(
            {
                "case_id": case_id,
                "exit_code": exit_code,
                "runtime_seconds": _parse_runtime(runtime_path),
                "sampling_score_records": len(score_lines),
                "clustered_models": len(models),
                "top_rank_receptor_frame_ca_rmsd_angstrom": models[0]["receptor_frame_ca_rmsd_angstrom"],
                "best_clustered_receptor_frame_ca_rmsd_angstrom": min(
                    model["receptor_frame_ca_rmsd_angstrom"] for model in models
                ),
                "top_rank_superposed_ca_rmsd_angstrom": models[0]["superposed_ca_rmsd_angstrom"],
                "models": models,
                "artifacts": {
                    str(path.relative_to(run_root)): {
                        "bytes": path.stat().st_size,
                        "sha256": _sha256(path),
                    }
                    for path in (predicted_path, scores_path, runtime_path, native_path)
                },
            }
        )
    analysis = {
        "schema_version": "frogent-mdockpep2-reference-redocking-analysis-v1",
        "status": "complete",
        "cases": cases,
        "case_count": len(cases),
        "mean_top_rank_receptor_frame_ca_rmsd_angstrom": float(
            np.mean([case["top_rank_receptor_frame_ca_rmsd_angstrom"] for case in cases])
        ),
        "claim_boundary": protocol["claim_boundary"],
    }
    analysis_root = run_root / "analysis"
    analysis_root.mkdir(exist_ok=True)
    analysis_path = analysis_root / "analysis.json"
    analysis_path.write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "frogent-mdockpep2-reference-redocking-final-v1",
        "status": "complete",
        "case_counts": {"exit_zero": len(cases), "scored": len(cases)},
        "analysis": {
            "path": str(analysis_path.relative_to(run_root)),
            "bytes": analysis_path.stat().st_size,
            "sha256": _sha256(analysis_path),
        },
        "claim_boundary": protocol["claim_boundary"],
    }
    (run_root / "final-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest["case_counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
