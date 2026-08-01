#!/usr/bin/env python3
"""Compare the primary and extension CBGBench cohorts without changing their protocol."""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


MODELS = ("targetdiff", "diffsbdd", "pocket2mol")
POCKETS = ("1IEP", "2HYY", "3CS9", "4WA9", "1M17")
PRIMARY_SEEDS = {17, 23, 31}
EXTENSION_SEEDS = {47, 59, 71}
METRICS = ("valid_rate", "qed_mean", "raw_rdkit_sa_mean")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary-manifest", type=Path, required=True)
    parser.add_argument("--extension-manifest", type=Path, required=True)
    parser.add_argument("--combined-manifest", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def mean(values: Iterable[float]) -> float:
    vals = list(values)
    return statistics.fmean(vals)


def sample_sd(values: Iterable[float]) -> float:
    vals = list(values)
    return statistics.stdev(vals) if len(vals) > 1 else 0.0


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    result = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i + 1
        while j < len(order) and values[order[j]] == values[order[i]]:
            j += 1
        rank = (i + 1 + j) / 2
        for index in order[i:j]:
            result[index] = rank
        i = j
    return result


def spearman(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    lr, rr = ranks(left), ranks(right)
    lm, rm = mean(lr), mean(rr)
    numerator = sum((x - lm) * (y - rm) for x, y in zip(lr, rr))
    denominator = math.sqrt(sum((x - lm) ** 2 for x in lr) * sum((y - rm) ** 2 for y in rr))
    return numerator / denominator if denominator else None


def normalized_job(job: dict[str, Any], cohort: str) -> dict[str, Any]:
    attempted = int(job["attempted_samples"])
    valid = int(job["valid_molecules"])
    return {
        "cohort": cohort,
        "model": job["method"],
        "pocket": job["pdb_id"].upper(),
        "seed": int(job["seed"]),
        "valid_molecules": valid,
        "attempted_samples": attempted,
        "valid_rate": valid / attempted,
        "qed_mean": float(job["qed_mean"]),
        "raw_rdkit_sa_mean": float(job["raw_rdkit_sa_mean"]),
        "reconstruction_errors": dict(job.get("reconstruction_errors") or {}),
        "exit_code": int(job["exit_code"]),
    }


def validate_jobs(jobs: list[dict[str, Any]]) -> None:
    expected = {(m, p, s) for m in MODELS for p in POCKETS for s in PRIMARY_SEEDS | EXTENSION_SEEDS}
    observed = {(j["model"], j["pocket"], j["seed"]) for j in jobs}
    if observed != expected or len(jobs) != 90:
        raise ValueError(f"six-seed job identity mismatch: missing={sorted(expected-observed)} extra={sorted(observed-expected)}")
    if any(job["exit_code"] != 0 for job in jobs):
        raise ValueError("six-seed matrix contains a nonzero job")


def cluster_bootstrap_delta(jobs: list[dict[str, Any]], model: str, metric: str) -> dict[str, Any]:
    pocket_delta: dict[str, float] = {}
    for pocket in POCKETS:
        primary = [j[metric] for j in jobs if j["model"] == model and j["pocket"] == pocket and j["cohort"] == "primary"]
        extension = [j[metric] for j in jobs if j["model"] == model and j["pocket"] == pocket and j["cohort"] == "extension"]
        pocket_delta[pocket] = mean(extension) - mean(primary)
    distribution = [mean(pocket_delta[pocket] for pocket in sample) for sample in itertools.product(POCKETS, repeat=len(POCKETS))]
    return {
        "delta_extension_minus_primary": mean(pocket_delta.values()),
        "ci95": [percentile(distribution, 0.025), percentile(distribution, 0.975)],
        "pocket_deltas": pocket_delta,
        "resamples": len(distribution),
        "pocket_wins_ties_losses": {
            "positive": sum(value > 0 for value in pocket_delta.values()),
            "zero": sum(value == 0 for value in pocket_delta.values()),
            "negative": sum(value < 0 for value in pocket_delta.values()),
        },
    }


def main() -> int:
    args = parse_args()
    paths = [args.primary_manifest.resolve(), args.extension_manifest.resolve(), args.combined_manifest.resolve(), args.protocol.resolve()]
    output_root = args.output_root.resolve()
    if output_root.exists():
        raise FileExistsError(output_root)
    if any(not path.is_file() for path in paths):
        raise FileNotFoundError([str(path) for path in paths if not path.is_file()])
    primary_data, extension_data, combined_data, protocol = (json.loads(path.read_text()) for path in paths)
    if primary_data.get("exit_zero_jobs") != 45 or extension_data.get("exit_zero_jobs") != 45 or combined_data.get("exit_zero_jobs") != 90:
        raise ValueError("terminal manifest validation failed")
    primary_jobs = [normalized_job(job, "primary") for job in primary_data["jobs"]]
    extension_jobs = [normalized_job(job, "extension") for job in extension_data["jobs"]]
    jobs = primary_jobs + extension_jobs
    validate_jobs(jobs)
    output_root.mkdir(parents=True)

    cell_rows: list[dict[str, Any]] = []
    for model in MODELS:
        for pocket in POCKETS:
            by_cohort = {
                cohort: [j for j in jobs if j["model"] == model and j["pocket"] == pocket and j["cohort"] == cohort]
                for cohort in ("primary", "extension")
            }
            row: dict[str, Any] = {"model": model, "pocket": pocket}
            for metric in METRICS:
                primary_values = [j[metric] for j in by_cohort["primary"]]
                extension_values = [j[metric] for j in by_cohort["extension"]]
                pooled = primary_values + extension_values
                row.update(
                    {
                        f"primary_{metric}_mean": mean(primary_values),
                        f"primary_{metric}_sd": sample_sd(primary_values),
                        f"extension_{metric}_mean": mean(extension_values),
                        f"extension_{metric}_sd": sample_sd(extension_values),
                        f"pooled_{metric}_mean": mean(pooled),
                        f"pooled_{metric}_sd": sample_sd(pooled),
                        f"delta_{metric}": mean(extension_values) - mean(primary_values),
                    }
                )
            cell_rows.append(row)
    cell_path = output_root / "model-pocket-stability.csv"
    with cell_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(cell_rows[0]))
        writer.writeheader()
        writer.writerows(cell_rows)

    model_results: dict[str, Any] = {}
    for model in MODELS:
        model_results[model] = {}
        for metric in METRICS:
            primary_values = [j[metric] for j in jobs if j["model"] == model and j["cohort"] == "primary"]
            extension_values = [j[metric] for j in jobs if j["model"] == model and j["cohort"] == "extension"]
            pooled = primary_values + extension_values
            model_results[model][metric] = {
                "primary_mean": mean(primary_values),
                "primary_sd": sample_sd(primary_values),
                "extension_mean": mean(extension_values),
                "extension_sd": sample_sd(extension_values),
                "pooled_mean": mean(pooled),
                "pooled_sd": sample_sd(pooled),
                "cluster_bootstrap": cluster_bootstrap_delta(jobs, model, metric),
            }

    rank_stability: dict[str, Any] = {}
    model_rankings: dict[str, Any] = {}
    for metric in METRICS:
        primary_cells = [row[f"primary_{metric}_mean"] for row in cell_rows]
        extension_cells = [row[f"extension_{metric}_mean"] for row in cell_rows]
        pooled_cells = [row[f"pooled_{metric}_mean"] for row in cell_rows]
        rank_stability[metric] = {
            "primary_vs_extension_spearman": spearman(primary_cells, extension_cells),
            "primary_vs_pooled_spearman": spearman(primary_cells, pooled_cells),
        }
        reverse = metric != "raw_rdkit_sa_mean"
        model_rankings[metric] = {}
        for cohort in ("primary", "extension", "pooled"):
            values = {model: model_results[model][metric][f"{cohort}_mean"] for model in MODELS}
            model_rankings[metric][cohort] = sorted(values, key=values.get, reverse=reverse)

    error_counter: dict[tuple[str, str, str, str], int] = Counter()
    attempts: dict[tuple[str, str, str], int] = Counter()
    for job in jobs:
        attempts[(job["cohort"], job["model"], job["pocket"])] += job["attempted_samples"]
        for error_type, count in job["reconstruction_errors"].items():
            error_counter[(job["cohort"], job["model"], job["pocket"], error_type)] += int(count)
    error_rows = []
    for (cohort, model, pocket, error_type), count in sorted(error_counter.items()):
        error_rows.append(
            {
                "cohort": cohort,
                "model": model,
                "pocket": pocket,
                "error_type": error_type,
                "count": count,
                "attempted_samples": attempts[(cohort, model, pocket)],
                "error_per_attempt": count / attempts[(cohort, model, pocket)],
            }
        )
    error_path = output_root / "reconstruction-errors.csv"
    with error_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(error_rows[0]) if error_rows else ["cohort", "model", "pocket", "error_type", "count", "attempted_samples", "error_per_attempt"])
        writer.writeheader()
        writer.writerows(error_rows)

    top_cell_shifts: dict[str, list[dict[str, Any]]] = {}
    for metric in METRICS:
        top_cell_shifts[metric] = sorted(
            ({"model": row["model"], "pocket": row["pocket"], "delta": row[f"delta_{metric}"]} for row in cell_rows),
            key=lambda item: abs(item["delta"]),
            reverse=True,
        )[:5]
    summary = {
        "schema_version": "frogent-cbgbench-six-seed-stability-summary-v1",
        "created_at": datetime.now().astimezone().isoformat(),
        "protocol": protocol,
        "terminal_jobs": 90,
        "model_results": model_results,
        "rank_stability": rank_stability,
        "model_rankings": model_rankings,
        "top_cell_shifts": top_cell_shifts,
        "interpretation": {
            "primary_remains_primary": True,
            "top_model_retained_for_valid_rate": model_rankings["valid_rate"]["primary"][0] == model_rankings["valid_rate"]["pooled"][0],
            "top_model_retained_for_qed": model_rankings["qed_mean"]["primary"][0] == model_rankings["qed_mean"]["pooled"][0],
            "top_model_retained_for_sa": model_rankings["raw_rdkit_sa_mean"]["primary"][0] == model_rankings["raw_rdkit_sa_mean"]["pooled"][0],
        },
    }
    summary_path = output_root / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    report_lines = [
        "# CBGBench six-seed stability analysis",
        "",
        f"- Terminal matrix: 90/90 jobs, with the original three seeds retained as primary.",
    ]
    for model in MODELS:
        q = model_results[model]["qed_mean"]
        v = model_results[model]["valid_rate"]
        report_lines.append(
            f"- {model}: QED {q['primary_mean']:.3f} -> {q['pooled_mean']:.3f}; valid rate {v['primary_mean']:.3f} -> {v['pooled_mean']:.3f}."
        )
    report_lines.extend(
        [
            "",
            "The pooled analysis is a post-outcome stability extension. Rank retention and pocket-level shifts are reported without replacing the primary result.",
        ]
    )
    report_path = output_root / "REPORT.md"
    report_path.write_text("\n".join(report_lines) + "\n")
    manifest = {
        "schema_version": "frogent-cbgbench-six-seed-stability-manifest-v1",
        "created_at": datetime.now().astimezone().isoformat(),
        "status": "complete",
        "terminal_jobs": 90,
        "outputs": [str(summary_path), str(cell_path), str(error_path), str(report_path)],
    }
    (output_root / "final-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
