#!/usr/bin/env python3
"""Render the clean ten-model panel as an editable heatmap plus macro summary."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ANALYSIS = (
    ROOT
    / "runtime/evaluation/revision-20260805/"
    "clean-ten-model-panel-budget-controlled-r03/analysis"
)
TASK_LABELS = {
    "foundational_biomedical_knowledge": "Knowledge",
    "retrieve_known_drugs": "Drug\nretrieval",
    "retrieve_known_targets": "Target\nretrieval",
    "molecular_property_prediction": "Property\nprediction",
    "virtual_screening": "Virtual\nscreening",
    "binding_mechanism": "Binding\nmechanism",
    "molecular_design": "Molecular\ndesign",
    "retrosynthesis_planning": "Retro-\nsynthesis",
}


def _bootstrap_interval(values: np.ndarray, seed: int) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    samples = rng.choice(values, size=(20_000, len(values)), replace=True).mean(axis=1)
    return tuple(float(value) for value in np.quantile(samples, [0.025, 0.975]))


def render(analysis_root: Path) -> list[Path]:
    summary = json.loads((analysis_root / "summary.json").read_text(encoding="utf-8"))
    models = [model["display_name"] for model in summary["models"]]
    model_ids = [model["model_id"] for model in summary["models"]]
    tasks = list(TASK_LABELS)
    scores = {
        (row["model_id"], row["task"]): row["score"]
        for row in summary["cells"]
        if isinstance(row.get("score"), (int, float))
    }
    matrix = np.array(
        [[scores.get((model_id, task), np.nan) for task in tasks] for model_id in model_ids],
        dtype=float,
    )

    means = np.nanmean(matrix, axis=1)
    intervals = np.array([
        _bootstrap_interval(row[np.isfinite(row)], 20260805 + index)
        if np.isfinite(row).any() else (np.nan, np.nan)
        for index, row in enumerate(matrix)
    ])

    figure = plt.figure(figsize=(7.09, 5.75))
    figure.subplots_adjust(top=0.79, bottom=0.18, left=0.22, right=0.98)
    grid = figure.add_gridspec(1, 2, width_ratios=[7.7, 2.0], wspace=0.08)
    heat = figure.add_subplot(grid[0, 0])
    macro = figure.add_subplot(grid[0, 1], sharey=heat)
    image = heat.imshow(np.ma.masked_invalid(matrix), cmap="cividis", vmin=0, vmax=1,
                        aspect="auto", interpolation="nearest")

    heat.set_xticks(np.arange(len(tasks)), [TASK_LABELS[task] for task in tasks],
                    fontsize=7)
    heat.set_yticks(np.arange(len(models)), models, fontsize=7.5)
    heat.tick_params(axis="x", top=True, labeltop=True, bottom=False, labelbottom=False,
                     length=0, pad=5)
    heat.tick_params(axis="y", length=0, pad=5)
    for row in range(len(models)):
        for column in range(len(tasks)):
            value = matrix[row, column]
            if np.isfinite(value):
                color = "white" if value < 0.48 else "black"
                heat.text(column, row, f"{value:.2f}", ha="center", va="center",
                          fontsize=6.2, color=color)
            else:
                heat.add_patch(Rectangle(
                    (column - 0.5, row - 0.5), 1, 1, facecolor="#eeeeee",
                    edgecolor="#999999", hatch="////", linewidth=0.35,
                ))
                heat.text(column, row, "NA", ha="center", va="center", fontsize=5.8,
                          color="#555555")
    heat.set_xticks(np.arange(-0.5, len(tasks), 1), minor=True)
    heat.set_yticks(np.arange(-0.5, len(models), 1), minor=True)
    heat.grid(which="minor", color="white", linewidth=0.8)
    heat.tick_params(which="minor", bottom=False, left=False)
    heat.set_title("A  Normalized task score", loc="left", fontsize=9.5,
                   fontweight="bold", pad=34)

    positions = np.arange(len(models))
    lower = means - intervals[:, 0]
    upper = intervals[:, 1] - means
    macro.errorbar(
        means, positions, xerr=np.vstack([lower, upper]), fmt="o", color="#0072B2",
        ecolor="#0072B2", elinewidth=1.0, capsize=2.0, markersize=3.8,
    )
    macro.axvline(0.5, color="#999999", linestyle="--", linewidth=0.75, zorder=0)
    macro.set_xlim(0, 1)
    macro.set_xticks([0, 0.5, 1.0])
    macro.tick_params(axis="x", top=True, labeltop=True, bottom=False, labelbottom=False,
                      labelsize=7, length=2, pad=4)
    macro.tick_params(axis="y", left=False, labelleft=False)
    macro.grid(axis="x", color="#dddddd", linewidth=0.6)
    macro.set_title("B  Macro mean\n95% task bootstrap CI", loc="left", fontsize=8.5,
                    fontweight="bold", pad=17)
    for index, mean in enumerate(means):
        if np.isfinite(mean):
            macro.text(min(mean + 0.035, 0.98), index, f"{mean:.2f}", va="center",
                       ha="left" if mean < 0.92 else "right", fontsize=6.3)

    colorbar = figure.colorbar(image, ax=[heat, macro], orientation="horizontal",
                              fraction=0.035, pad=0.055, aspect=45)
    colorbar.set_label("Score (higher is better)", fontsize=7.5)
    colorbar.ax.tick_params(labelsize=6.5, length=2)
    figure.suptitle(
        "Clean no-tool comparison on eight exposed benchmark tasks",
        x=0.08, y=0.985, ha="left", fontsize=10.5, fontweight="bold",
    )
    figure.text(
        0.08, 0.015,
        "Each cell aggregates 20 author-supplied cases. Gold answers were withheld during "
        "inference. GPT models used low reasoning; five OpenRouter reasoning-first models "
        "used the preregistered no-reasoning compatibility amendment.",
        fontsize=6.4, ha="left", va="bottom",
    )

    output_root = analysis_root / "figure"
    output_root.mkdir(parents=True, exist_ok=True)
    outputs = [
        output_root / "clean-ten-model-panel.png",
        output_root / "clean-ten-model-panel.pdf",
        output_root / "clean-ten-model-panel.svg",
    ]
    figure.savefig(outputs[0], dpi=320, bbox_inches="tight", facecolor="white")
    figure.savefig(outputs[1], bbox_inches="tight", facecolor="white")
    figure.savefig(outputs[2], bbox_inches="tight", facecolor="white")
    plt.close(figure)

    rows = []
    for index, model_id in enumerate(model_ids):
        rows.append({
            "display_name": models[index],
            "model_id": model_id,
            "macro_mean": means[index],
            "bootstrap_ci_low": intervals[index, 0],
            "bootstrap_ci_high": intervals[index, 1],
            "scored_tasks": int(np.isfinite(matrix[index]).sum()),
        })
    with (analysis_root / "model-summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-root", type=Path, default=DEFAULT_ANALYSIS)
    args = parser.parse_args()
    analysis_root = args.analysis_root.resolve()
    try:
        analysis_root.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("analysis root must stay inside the FROGENT project") from exc
    outputs = render(analysis_root)
    print("\n".join(str(path.relative_to(ROOT)) for path in outputs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
