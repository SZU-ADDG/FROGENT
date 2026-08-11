#!/usr/bin/env python3
"""Score and plot direct-model versus same-base-model FROGENT effects."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt
import matplotlib.patheffects as path_effects
import numpy as np
from matplotlib.colors import TwoSlopeNorm

from score_clean_ten_model_panel import SOURCE_ROOT, score

DEFAULT_DIRECT = (
    ROOT
    / "runtime/evaluation/revision-20260805/"
    "clean-twelve-model-panel-direct-extension-r18/analysis/summary.json"
)
DEFAULT_FROGENT = (
    ROOT
    / "runtime/evaluation/revision-20260805/"
    "paired-twelve-model-frogent-r20"
)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "display_name", "model_id", "task", "direct_score", "frogent_score", "delta"
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_case_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "task",
        "case_index",
        "cluster_id",
        "direct_mean",
        "frogent_mean",
        "mean_delta",
        "paired_models",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _read_source_csv(name: str) -> list[dict[str, str]]:
    with (SOURCE_ROOT / name).open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _case_cluster_ids(task: str, case_indices: list[int]) -> dict[int, str]:
    """Return frozen target/pocket clusters, falling back to independent cases."""

    source_spec = {
        "retrieve_known_drugs": ("test_data2.csv", "question"),
        "retrieve_known_targets": ("test_data3.csv", "question"),
        "molecular_property_prediction": ("test_data4.csv", "smiles"),
        "virtual_screening": ("test_data5.csv", "questions"),
        "binding_mechanism": ("test_data6.csv", "protein"),
        "retrosynthesis_planning": ("test_data8.csv", "smiles"),
    }.get(task)
    if source_spec is None:
        return {index: f"{task}:case:{index}" for index in case_indices}
    filename, field = source_spec
    rows = _read_source_csv(filename)
    clusters = {}
    for index in case_indices:
        value = rows[index - 1].get(field, "").strip()
        clusters[index] = (
            f"{task}:{field}:{value.casefold()}"
            if value
            else f"{task}:case:{index}"
        )
    return clusters


def _cluster_bootstrap(
    values_by_case: dict[int, float],
    clusters_by_case: dict[int, str],
    *,
    rng: np.random.Generator,
    iterations: int,
) -> dict[str, Any]:
    """Bootstrap case deltas by frozen target/pocket cluster."""

    grouped: dict[str, list[float]] = defaultdict(list)
    for case_index, value in values_by_case.items():
        grouped[clusters_by_case[case_index]].append(float(value))
    cluster_ids = sorted(grouped)
    observed = float(np.mean([value for values in grouped.values() for value in values]))
    samples = np.empty(iterations, dtype=float)
    for iteration in range(iterations):
        selected = rng.choice(cluster_ids, size=len(cluster_ids), replace=True)
        sampled = [value for cluster_id in selected for value in grouped[str(cluster_id)]]
        samples[iteration] = float(np.mean(sampled))
    lower, upper = np.quantile(samples, [0.025, 0.975])
    return {
        "observed_mean_delta": observed,
        "ci95": [float(lower), float(upper)],
        "clusters": len(cluster_ids),
        "cases": len(values_by_case),
        "bootstrap_samples": samples,
    }


def _paired_case_statistics(
    direct_details: list[dict[str, Any]],
    frogent_details: list[dict[str, Any]],
    tasks: list[str],
    *,
    seed: int = 20260805,
    iterations: int = 10000,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    direct = {
        (row["model_id"], row["task"], int(row["case_index"])): row
        for row in direct_details
        if isinstance(row.get("score"), (int, float))
    }
    frogent = {
        (row["model_id"], row["task"], int(row["case_index"])): row
        for row in frogent_details
        if isinstance(row.get("score"), (int, float))
    }
    grouped: dict[tuple[str, int], list[tuple[float, float]]] = defaultdict(list)
    for key, direct_row in direct.items():
        frogent_row = frogent.get(key)
        if frogent_row is None:
            continue
        grouped[(key[1], key[2])].append(
            (float(direct_row["score"]), float(frogent_row["score"]))
        )

    case_rows: list[dict[str, Any]] = []
    task_bootstrap: dict[str, dict[str, Any]] = {}
    rng = np.random.default_rng(seed)
    for task in tasks:
        task_cases = sorted(
            case_index for grouped_task, case_index in grouped if grouped_task == task
        )
        clusters = _case_cluster_ids(task, task_cases)
        values = {}
        for case_index in task_cases:
            pairs = grouped[(task, case_index)]
            direct_mean = float(np.mean([pair[0] for pair in pairs]))
            frogent_mean = float(np.mean([pair[1] for pair in pairs]))
            delta = frogent_mean - direct_mean
            values[case_index] = delta
            case_rows.append({
                "task": task,
                "case_index": case_index,
                "cluster_id": clusters[case_index],
                "direct_mean": direct_mean,
                "frogent_mean": frogent_mean,
                "mean_delta": delta,
                "paired_models": len(pairs),
            })
        task_bootstrap[task] = _cluster_bootstrap(
            values,
            clusters,
            rng=rng,
            iterations=iterations,
        )

    overall_samples = np.mean(
        np.vstack([task_bootstrap[task]["bootstrap_samples"] for task in tasks]),
        axis=0,
    )
    overall_lower, overall_upper = np.quantile(overall_samples, [0.025, 0.975])
    statistics = {
        "schema_version": "frogent-paired-case-cluster-bootstrap-v1",
        "estimand": (
            "Macro mean across eight tasks of the case-level FROGENT-minus-direct "
            "delta, averaging the fixed 12-model panel within each exposed case."
        ),
        "inference_scope": (
            "Exposed benchmark cases for the fixed model panel; this is not a claim "
            "about unseen tasks, providers, or biological efficacy."
        ),
        "bootstrap": {
            "seed": seed,
            "iterations": iterations,
            "resampling_unit": "target_or_pocket_cluster_within_task",
            "ci": "percentile_95",
        },
        "overall": {
            "observed_mean_delta": float(np.mean([
                task_bootstrap[task]["observed_mean_delta"] for task in tasks
            ])),
            "ci95": [float(overall_lower), float(overall_upper)],
            "tasks": len(tasks),
            "case_task_units": len(case_rows),
        },
        "tasks": {
            task: {
                key: value
                for key, value in task_bootstrap[task].items()
                if key != "bootstrap_samples"
            }
            for task in tasks
        },
    }
    return case_rows, statistics


def _plot(summary: dict[str, Any], output_root: Path) -> None:
    models = summary["models"]
    tasks = summary["tasks"]
    names = [row["display_name"] for row in models]
    direct = [row["direct_macro_mean"] for row in models]
    frogent = [row["frogent_macro_mean"] for row in models]
    matrix = np.full((len(models), len(tasks)), np.nan)
    model_index = {row["model_id"]: index for index, row in enumerate(models)}
    task_index = {task: index for index, task in enumerate(tasks)}
    for row in summary["paired_cells"]:
        if isinstance(row["delta"], (int, float)):
            matrix[model_index[row["model_id"]], task_index[row["task"]]] = row["delta"]

    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 9,
        "axes.titlesize": 11,
        "axes.labelsize": 9.5,
        "xtick.labelsize": 8.5,
        "ytick.labelsize": 8.5,
        "legend.fontsize": 8.5,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
    })
    fig = plt.figure(figsize=(15.8, 8.7), constrained_layout=True)
    grid = fig.add_gridspec(1, 2, width_ratios=[1.0, 2.2])
    ax0 = fig.add_subplot(grid[0, 0])
    y = np.arange(len(models))
    width = 0.36
    direct_bars = ax0.barh(
        y - width / 2,
        [np.nan if value is None else value for value in direct],
        height=width,
        label="Direct model",
        color="#4E79A7",
    )
    frogent_bars = ax0.barh(
        y + width / 2,
        [np.nan if value is None else value for value in frogent],
        height=width,
        label="FROGENT",
        color="#E76F51",
    )
    ax0.set_yticks(y, names)
    ax0.invert_yaxis()
    ax0.set_xlim(0, 1)
    ax0.set_xlabel("Macro mean across eight tasks")
    ax0.set_title("System-level model effect")
    ax0.grid(axis="x", color="#D9D9D9", linewidth=0.7)
    ax0.set_axisbelow(True)
    ax0.legend(loc="lower right", frameon=False)
    ax0.bar_label(direct_bars, fmt="%.2f", padding=2, fontsize=7.2, color="#273444")
    ax0.bar_label(frogent_bars, fmt="%.2f", padding=2, fontsize=7.2, color="#6A2818")
    ax0.text(
        -0.16,
        1.035,
        "a",
        transform=ax0.transAxes,
        fontsize=12,
        fontweight="bold",
        va="bottom",
    )

    ax1 = fig.add_subplot(grid[0, 1])
    norm = TwoSlopeNorm(vmin=-0.5, vcenter=0.0, vmax=0.5)
    image = ax1.imshow(matrix, aspect="auto", cmap="RdBu_r", norm=norm)
    ax1.set_yticks(np.arange(len(models)), names)
    short_tasks = [
        "Knowledge", "Known drugs", "Known targets", "Properties",
        "Screening", "Mechanism", "Design", "Retrosynthesis",
    ]
    ax1.set_xticks(np.arange(len(tasks)), short_tasks, rotation=36, ha="right")
    ax1.set_title("FROGENT − direct score by task")
    ax1.set_xticks(np.arange(-0.5, len(tasks), 1), minor=True)
    ax1.set_yticks(np.arange(-0.5, len(models), 1), minor=True)
    ax1.grid(which="minor", color="white", linewidth=1.4)
    ax1.tick_params(which="minor", bottom=False, left=False)
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            value = matrix[row, column]
            if math.isfinite(value):
                rgba = image.cmap(image.norm(value))
                luminance = 0.2126 * rgba[0] + 0.7152 * rgba[1] + 0.0722 * rgba[2]
                dark_background = luminance < 0.52
                text_color = "white" if dark_background else "#111111"
                halo_color = "#202020" if dark_background else "white"
                annotation = ax1.text(
                    column,
                    row,
                    f"{value:+.2f}",
                    ha="center",
                    va="center",
                    fontsize=8.2,
                    fontweight="semibold",
                    color=text_color,
                )
                annotation.set_path_effects([
                    path_effects.Stroke(linewidth=1.6, foreground=halo_color),
                    path_effects.Normal(),
                ])
    colorbar = fig.colorbar(
        image,
        ax=ax1,
        shrink=0.76,
        pad=0.025,
        ticks=[-0.5, -0.25, 0.0, 0.25, 0.5],
    )
    colorbar.set_label("Paired score delta (FROGENT − direct)")
    ax1.text(
        -0.075,
        1.035,
        "b",
        transform=ax1.transAxes,
        fontsize=12,
        fontweight="bold",
        va="bottom",
    )
    fig.suptitle(
        "Base-model performance before and after FROGENT",
        fontsize=15,
        fontweight="semibold",
    )
    figure_root = output_root / "figure"
    figure_root.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "pdf", "svg"):
        fig.savefig(
            figure_root / f"paired-model-frogent-effect.{suffix}",
            dpi=600 if suffix == "png" else None,
            facecolor="white",
            bbox_inches="tight",
        )
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--direct-summary", type=Path, default=DEFAULT_DIRECT)
    parser.add_argument(
        "--frogent-roots",
        nargs="+",
        type=Path,
        default=[DEFAULT_FROGENT],
        help="Primary FROGENT run followed by ordered exact-cell recovery roots",
    )
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()
    direct_path = args.direct_summary.resolve()
    frogent_roots = [path.resolve() for path in args.frogent_roots]
    frogent_root = frogent_roots[0]
    output_root = (args.output_root or (frogent_root / "analysis")).resolve()
    for path in (direct_path, *frogent_roots, output_root):
        path.relative_to(ROOT.resolve())
    output_root.mkdir(parents=True, exist_ok=True)
    direct = json.loads(direct_path.read_text(encoding="utf-8"))
    direct_details = json.loads(
        (direct_path.parent / "per-case.json").read_text(encoding="utf-8")
    )
    frogent_details, frogent = score(frogent_roots)
    direct_cells = {
        (row["model_id"], row["task"]): row for row in direct["cells"]
    }
    frogent_cells = {
        (row["model_id"], row["task"]): row for row in frogent["cells"]
    }
    paired = []
    for key, direct_cell in direct_cells.items():
        frogent_cell = frogent_cells[key]
        direct_score = direct_cell.get("score")
        frogent_score = frogent_cell.get("score")
        delta = (
            float(frogent_score) - float(direct_score)
            if isinstance(direct_score, (int, float))
            and isinstance(frogent_score, (int, float))
            else None
        )
        paired.append({
            "display_name": direct_cell["display_name"],
            "model_id": key[0],
            "task": key[1],
            "direct_score": direct_score,
            "frogent_score": frogent_score,
            "delta": delta,
        })
    paired_by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in paired:
        paired_by_model[row["model_id"]].append(row)
    models = []
    for model in direct["models"]:
        rows = paired_by_model[model["model_id"]]
        deltas = [float(row["delta"]) for row in rows if isinstance(row["delta"], (int, float))]
        frogent_scores = [
            float(row["frogent_score"]) for row in rows
            if isinstance(row["frogent_score"], (int, float))
        ]
        models.append({
            "display_name": model["display_name"],
            "model_id": model["model_id"],
            "direct_macro_mean": model.get("macro_mean"),
            "frogent_macro_mean": (
                sum(frogent_scores) / len(frogent_scores)
                if len(frogent_scores) == len(direct["models"][0:1]) * 8 else None
            ),
            "paired_tasks": len(deltas),
            "mean_delta": sum(deltas) / len(deltas) if len(deltas) == 8 else None,
        })
    tasks = [task for task in json.loads(
        (frogent_root / "protocol/protocol.json").read_text(encoding="utf-8")
    )["tasks"]]
    case_rows, statistics = _paired_case_statistics(
        direct_details,
        frogent_details,
        tasks,
    )
    summary = {
        "schema_version": "frogent-paired-model-effect-v1",
        "status": "complete" if all(row["paired_tasks"] == 8 for row in models) else "partial",
        "tasks": tasks,
        "models": models,
        "paired_cells": paired,
        "statistics": statistics,
        "frogent_cell_counts": frogent["cell_counts"],
        "frogent_run_roots": frogent["run_roots"],
        "claim_boundary": (
            "Paired exposed-case comparison of direct model inference against the same exact "
            "base model inside the frozen FROGENT tool-evidence workflow."
        ),
    }
    (output_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_root / "frogent-per-case.json").write_text(
        json.dumps(frogent_details, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_csv(output_root / "paired-cells.csv", paired)
    _write_case_csv(output_root / "paired-case-deltas.csv", case_rows)
    (output_root / "paired-case-statistics.json").write_text(
        json.dumps(statistics, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _plot(summary, output_root)
    if summary["status"] == "complete":
        manifest = {
            "schema_version": "frogent-paired-model-final-manifest-v1",
            "status": "complete",
            "paired_cells": len(paired),
            "frogent_cell_counts": frogent["cell_counts"],
            "frogent_run_roots": frogent["run_roots"],
            "direct_summary": str(direct_path.relative_to(ROOT)),
            "analysis_files": [
                "summary.json",
                "paired-cells.csv",
                "paired-case-deltas.csv",
                "paired-case-statistics.json",
                "frogent-per-case.json",
                "figure/paired-model-frogent-effect.png",
                "figure/paired-model-frogent-effect.pdf",
                "figure/paired-model-frogent-effect.svg",
            ],
            "claim_boundary": summary["claim_boundary"],
        }
        (output_root / "final-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({
        "status": summary["status"],
        "paired_cells": sum(row["delta"] is not None for row in paired),
        "frogent_cell_counts": frogent["cell_counts"],
    }, sort_keys=True))
    return 0 if summary["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
