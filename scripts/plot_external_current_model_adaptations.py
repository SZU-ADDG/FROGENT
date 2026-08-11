#!/usr/bin/env python3
"""Plot direct-model, selected FROGENT, and public-system task scores."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch, Rectangle


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_ROOT = ROOT / (
    "runtime/evaluation/revision-20260810/external-sol-resource-enabled-recovery-r05"
)
DEFAULT_OUTPUT_ROOT = ROOT / "docs/manuscript/revision-source/figures"
EXTERNAL_SYSTEMS = ["CLADD", "Prompt-to-Pill", "Robin"]
TASKS = [
    ("foundational_biomedical_knowledge", "Foundational\nknowledge"),
    ("retrieve_known_drugs", "Known-drug\nretrieval"),
    ("retrieve_known_targets", "Known-target\nretrieval"),
    ("molecular_property_prediction", "Property\nprediction"),
    ("virtual_screening", "Virtual\nscreening"),
    ("binding_mechanism", "Binding\nmechanism"),
    ("molecular_design", "Molecular\ndesign"),
    ("retrosynthesis_planning", "Retrosynthesis"),
]


def _selected_frogent_scores() -> dict[str, float]:
    """Load the verified current FROGENT endpoint for all eight tasks."""

    paired = json.loads((ROOT / (
        "runtime/evaluation/revision-20260805/"
        "paired-twelve-model-frogent-final-r42/analysis/summary.json"
    )).read_text(encoding="utf-8"))
    scores = {
        cell["task"]: float(cell["frogent_score"])
        for cell in paired["paired_cells"]
        if cell["model_id"] == "gpt-5.6-sol"
    }
    chemistry = json.loads((ROOT / (
        "runtime/evaluation/revision-20260811/frogent-sol-max-chemistry-mcp-r01/"
        "analysis/summary.json"
    )).read_text(encoding="utf-8"))
    scores.update({
        row["task"]: float(row["score"])
        for row in chemistry["cells"]
        if row["status"] == "scored"
    })
    retrieval_runs = {
        "retrieve_known_drugs": "frogent-structured-binding-known-drug-r02",
        "retrieve_known_targets": "frogent-structured-binding-known-target-r02",
    }
    for task, run_name in retrieval_runs.items():
        result = json.loads((
            ROOT / "runtime/evaluation/revision-20260811" / run_name /
            "analysis/summary.json"
        ).read_text(encoding="utf-8"))
        if result.get("status") != "complete":
            raise ValueError(f"FROGENT retrieval result is incomplete: {task}")
        scores[task] = float(result["score"])
    missing = [task for task, _ in TASKS if task not in scores]
    if missing:
        raise ValueError(f"missing selected FROGENT scores: {missing}")
    return scores


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    run_root = args.run_root.resolve()
    run_root.relative_to(ROOT)
    output_root = args.output_root.resolve()
    output_root.relative_to(ROOT)
    output_root.mkdir(parents=True, exist_ok=True)
    summary = json.loads(
        (run_root / "analysis/combined-summary.json").read_text(encoding="utf-8")
    )
    lookup = {(cell["system"], cell["task"]): cell for cell in summary["cells"]}
    direct_path = ROOT / (
        "runtime/evaluation/revision-20260805/clean-twelve-model-panel-final-r33/"
        "analysis/cells.csv"
    )
    direct_rows = list(csv.DictReader(direct_path.open(encoding="utf-8")))
    direct_models = list(dict.fromkeys(row["display_name"] for row in direct_rows))
    if len(direct_models) != 12:
        raise ValueError(f"expected 12 direct models, found {len(direct_models)}")
    systems = [*direct_models, *EXTERNAL_SYSTEMS, "FROGENT"]
    values = np.full((len(systems), len(TASKS)), np.nan)
    denominators = np.full(values.shape, "", dtype=object)

    for row_index, model_name in enumerate(direct_models):
        for column, (task, _) in enumerate(TASKS):
            matches = [
                row
                for row in direct_rows
                if row["display_name"] == model_name and row["task"] == task
            ]
            if len(matches) != 1:
                raise ValueError(f"expected one direct cell for {model_name}/{task}")
            values[row_index, column] = float(matches[0]["score"])
            denominators[row_index, column] = f"n={int(matches[0]['measured_cases'])}"

    external_start_index = len(direct_models)
    frogent_row_index = external_start_index + len(EXTERNAL_SYSTEMS)
    frogent_scores = _selected_frogent_scores()
    for column, (task, _) in enumerate(TASKS):
        if task not in frogent_scores:
            raise ValueError(f"missing selected FROGENT score for {task}")
        values[frogent_row_index, column] = frogent_scores[task]
        denominators[frogent_row_index, column] = (
            "n=19" if task == "virtual_screening" else "n=20"
        )

    for row, system in enumerate(EXTERNAL_SYSTEMS, start=external_start_index):
        for column, (task, _) in enumerate(TASKS):
            cell = lookup.get((system, task))
            if cell and cell["status"] == "scored":
                values[row, column] = float(cell["score"])
                denominators[row, column] = f"n={int(cell['measured_cases'])}"

    comparison_rows = []
    for row, system in enumerate(EXTERNAL_SYSTEMS, start=external_start_index):
        for column, (task, task_label) in enumerate(TASKS):
            external_score = values[row, column]
            if np.isnan(external_score):
                continue
            frogent_score = values[frogent_row_index, column]
            delta = float(external_score - frogent_score)
            comparison_rows.append({
                "external_system": system,
                "task": task,
                "task_label": task_label.replace("\n", " "),
                "external_score": float(external_score),
                "frogent_score": float(frogent_score),
                "external_minus_frogent": delta,
                "higher_score": system if delta > 0 else "FROGENT" if delta < 0 else "tie",
            })
    comparison_path = run_root / "analysis/external-vs-selected-frogent.csv"
    with comparison_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(comparison_rows[0]))
        writer.writeheader()
        writer.writerows(comparison_rows)

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 8,
            "axes.titlesize": 9,
            "xtick.labelsize": 7,
            "ytick.labelsize": 6.6,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
        }
    )
    fig, ax = plt.subplots(figsize=(10.8, 7.0), constrained_layout=True)
    ax.set_xlim(-0.5, len(TASKS) - 0.5)
    ax.set_ylim(len(systems) - 0.5, -0.5)
    ax.set_xticks(range(len(TASKS)), [label for _, label in TASKS])
    ax.set_yticks(range(len(systems)), systems)
    ax.tick_params(length=0)
    direct_color = "#718CA6"
    frogent_color = "#D55E00"
    external_color = "#009E73"
    track_color = "#EDF1F4"
    missing_color = "#F7F7F7"
    border_color = "#D8DDE2"
    bar_left = -0.40
    bar_width = 0.60
    bar_height = 0.38
    for row in range(len(systems)):
        if row < external_start_index:
            bar_color = direct_color
        elif row < frogent_row_index:
            bar_color = external_color
        else:
            bar_color = frogent_color
        for column in range(len(TASKS)):
            value = values[row, column]
            cell = Rectangle(
                (column - 0.5, row - 0.5),
                1,
                1,
                facecolor="white",
                edgecolor=border_color,
                linewidth=0.7,
                zorder=0,
            )
            ax.add_patch(cell)
            if np.isnan(value):
                cell.set_facecolor(missing_color)
                cell.set_hatch("////")
                ax.text(
                    column,
                    row,
                    "—",
                    ha="center",
                    va="center",
                    color="#747474",
                    fontsize=7.5,
                    zorder=3,
                )
            else:
                ax.add_patch(
                    Rectangle(
                        (column + bar_left, row - bar_height / 2),
                        bar_width,
                        bar_height,
                        facecolor=track_color,
                        edgecolor="none",
                        zorder=1,
                    )
                )
                ax.add_patch(
                    Rectangle(
                        (column + bar_left, row - bar_height / 2),
                        bar_width * value,
                        bar_height,
                        facecolor=bar_color,
                        edgecolor="none",
                        zorder=2,
                    )
                )
                ax.text(
                    column + 0.42,
                    row,
                    f"{value:.3f}",
                    ha="right",
                    va="center",
                    color="#202124",
                    fontsize=6.2,
                    zorder=3,
                )
    ax.axhline(len(direct_models) - 0.5, color="#222222", linewidth=1.4)
    ax.axhline(frogent_row_index - 0.5, color="#222222", linewidth=1.4)
    ax.get_yticklabels()[frogent_row_index].set_fontweight("bold")
    for spine in ax.spines.values():
        spine.set_linewidth(0.8)
        spine.set_color("#222222")
    ax.legend(
        handles=[
            Patch(facecolor=direct_color, label="Direct LLM"),
            Patch(facecolor=frogent_color, label="FROGENT"),
            Patch(facecolor=external_color, label="External agent system"),
            Patch(facecolor=missing_color, edgecolor="#AAAAAA", hatch="////", label="Task not implemented"),
        ],
        loc="lower center",
        bbox_to_anchor=(0.5, 1.005),
        ncol=4,
        frameon=False,
        fontsize=6.2,
        handlelength=1.5,
        columnspacing=1.2,
    )
    base = output_root / "external-current-model-adaptations"
    for suffix in ("svg", "pdf", "png"):
        fig.savefig(
            base.with_suffix(f".{suffix}"),
            dpi=600 if suffix == "png" else None,
            bbox_inches="tight",
            facecolor="white",
        )
    plt.close(fig)
    print(base)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
