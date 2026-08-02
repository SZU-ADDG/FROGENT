#!/usr/bin/env python3
import csv
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

try:
    from scipy.stats import wilcoxon
except Exception:  # pragma: no cover - the manifest preserves an explicit null
    wilcoxon = None

METRICS = (
    "valid_rate",
    "unique_valid_rate",
    "top50_score_mean",
    "top50_qed_mean",
    "top50_favorable_sa_mean",
)
CONDITION_PAIRS = (
    ("fixed_best", "single_pass"),
    ("fixed_best", "iterative"),
    ("single_pass", "iterative"),
)


def tsv_rows(path: Path):
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def load_job(run_root: Path, row: dict) -> dict:
    tag = row["tag"]
    state = run_root / "state" / "jobs" / tag
    exit_code = int((state / "exit_code").read_text().strip())
    summary = json.loads((run_root / "results" / tag / "run_summary.json").read_text()) if exit_code == 0 else {}
    scored = []
    csv_path = run_root / "results" / tag / "generated_smiles_qed_sa.csv"
    if exit_code == 0 and csv_path.exists():
        with csv_path.open(newline="") as handle:
            for item in csv.DictReader(handle):
                qed = float(item["QED"])
                sa = float(item["SA_score"])
                scored.append({"smiles": item["smiles"], "qed": qed, "sa": sa, "score": 0.70 * qed + 0.30 * sa})
    return {
        **row,
        "seed": int(row["seed"]),
        "num_samples": int(row["num_samples"]),
        "exit_code": exit_code,
        "summary": summary,
        "scored": scored,
        "started_at": (state / "started_at").read_text().strip(),
        "finished_at": (state / "finished_at").read_text().strip(),
        "gpu": int((state / "gpu").read_text().strip()),
    }


def cell_summary(condition: str, pocket: str, seed: int, jobs: list[dict]) -> dict:
    attempted = sum(job["num_samples"] for job in jobs)
    valid = sum(int(job["summary"].get("valid_molecules", 0)) for job in jobs)
    scored = [item for job in jobs for item in job["scored"]]
    unique = len({item["smiles"] for item in scored})
    top = sorted(scored, key=lambda item: item["score"], reverse=True)[:50]
    errors = Counter()
    for job in jobs:
        errors.update(job["summary"].get("reconstruction_errors", {}))
    mean = lambda key: statistics.fmean(item[key] for item in top) if top else None
    return {
        "condition": condition,
        "pocket": pocket,
        "seed": seed,
        "attempted_samples": attempted,
        "valid_molecules": valid,
        "unique_valid_smiles": unique,
        "valid_rate": valid / attempted,
        "unique_valid_rate": unique / attempted,
        "top_k": len(top),
        "top50_score_mean": mean("score"),
        "top50_qed_mean": mean("qed"),
        "top50_favorable_sa_mean": mean("sa"),
        "method_attempt_allocation": dict(
            Counter({method: sum(job["num_samples"] for job in jobs if job["method"] == method) for method in {job["method"] for job in jobs}})
        ),
        "reconstruction_errors": dict(errors),
        "job_tags": [job["tag"] for job in jobs],
    }


def pocket_bootstrap(diffs: list[tuple[str, float]], draws: int = 10000) -> list[float]:
    grouped = defaultdict(list)
    for pocket, value in diffs:
        grouped[pocket].append(value)
    pockets = sorted(grouped)
    rng = random.Random(20260802)
    samples = []
    for _ in range(draws):
        chosen = [rng.choice(pockets) for _ in pockets]
        values = [value for pocket in chosen for value in grouped[pocket]]
        samples.append(statistics.fmean(values))
    samples.sort()
    return [samples[math.floor(0.025 * draws)], samples[math.floor(0.975 * draws) - 1]]


def paired_comparison(cells: list[dict], first: str, second: str, metric: str) -> dict:
    lookup = {(cell["condition"], cell["pocket"], cell["seed"]): cell for cell in cells}
    diffs = []
    for pocket in sorted({cell["pocket"] for cell in cells}):
        for seed in sorted({cell["seed"] for cell in cells if cell["pocket"] == pocket}):
            left = lookup[(first, pocket, seed)][metric]
            right = lookup[(second, pocket, seed)][metric]
            if left is not None and right is not None:
                diffs.append((pocket, right - left))
    values = [value for _, value in diffs]
    p_value = None
    if wilcoxon is not None and values and any(value != 0 for value in values):
        p_value = float(wilcoxon(values, alternative="two-sided", zero_method="wilcox").pvalue)
    return {
        "contrast": f"{second} - {first}",
        "metric": metric,
        "paired_cells": len(values),
        "mean_difference": statistics.fmean(values),
        "median_difference": statistics.median(values),
        "positive_cells": sum(value > 0 for value in values),
        "negative_cells": sum(value < 0 for value in values),
        "zero_cells": sum(value == 0 for value in values),
        "wilcoxon_two_sided_p": p_value,
        "pocket_cluster_bootstrap_95_ci": pocket_bootstrap(diffs),
    }


def main() -> None:
    run_root = Path(__file__).resolve().parents[1]
    rows = tsv_rows(run_root / "protocol" / "phase1-jobs.tsv") + tsv_rows(run_root / "protocol" / "phase2-jobs.tsv")
    jobs = [load_job(run_root, row) for row in rows]
    if len(jobs) != 120 or any(job["exit_code"] != 0 for job in jobs):
        raise SystemExit("finalization requires 120 exit-zero jobs")

    cells = []
    for pocket in ("1IEP", "2HYY", "3CS9", "4WA9", "1M17"):
        for seed in (83, 97, 109):
            cells.append(cell_summary("fixed_best", pocket, seed, [job for job in jobs if job["condition"] == "fixed_best" and job["pocket"] == pocket and job["seed"] == seed]))
            cells.append(cell_summary("single_pass", pocket, seed, [job for job in jobs if job["condition"] == "single_pass" and job["pocket"] == pocket and job["seed"] == seed]))
            iterative_jobs = [job for job in jobs if job["condition"] == "iterative" and job["pocket"] == pocket and (job["seed"] == seed or (job["stage"] == "round2" and job["seed"] == seed + 10000))]
            cells.append(cell_summary("iterative", pocket, seed, iterative_jobs))

    condition_summary = {}
    for condition in ("fixed_best", "single_pass", "iterative"):
        selected = [cell for cell in cells if cell["condition"] == condition]
        condition_summary[condition] = {
            "cells": len(selected),
            "attempted_samples": sum(cell["attempted_samples"] for cell in selected),
            "valid_molecules": sum(cell["valid_molecules"] for cell in selected),
            **{metric: statistics.fmean(cell[metric] for cell in selected if cell[metric] is not None) for metric in METRICS},
        }

    comparisons = [paired_comparison(cells, first, second, metric) for first, second in CONDITION_PAIRS for metric in METRICS]
    decisions = json.loads((run_root / "gauge-decisions.json").read_text())["decisions"]
    manifest = {
        "status": "complete",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "protocol_id": "forge-gauge-matched-budget-prospective-r02",
        "expected_jobs": 120,
        "exit_zero_jobs": 120,
        "pockets": 5,
        "prospective_seeds": [83, 97, 109],
        "paired_cells_per_condition": 15,
        "condition_summary": condition_summary,
        "gauge_selected_model_counts": dict(Counter(item["selected_method"] for item in decisions)),
        "paired_comparisons": comparisons,
        "cells": cells,
        "jobs": [{key: job[key] for key in ("tag", "condition", "stage", "method", "pocket", "seed", "num_samples", "exit_code", "gpu", "started_at", "finished_at")} for job in jobs],
        "claim_boundary": "Matched-budget deterministic model routing and one feedback-driven allocation step only; no experimental affinity or unconstrained refinement claim.",
    }
    output = run_root / "final-manifest.json"
    output.write_text(json.dumps(manifest, indent=2) + "\n")
    print(output)


if __name__ == "__main__":
    main()
