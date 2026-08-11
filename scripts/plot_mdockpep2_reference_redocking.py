#!/usr/bin/env python3
"""Plot the frozen MDockPeP2 reference-redocking summary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_ROOT = ROOT / (
    "runtime/evaluation/revision-20260807/mdockpep2-reference-redocking-r01"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    args = parser.parse_args()
    run_root = args.run_root.resolve()
    run_root.relative_to(ROOT)
    analysis = json.loads(
        (run_root / "analysis/analysis.json").read_text(encoding="utf-8")
    )
    cases = analysis["cases"]
    labels = [case["case_id"].upper() for case in cases]
    top_one = [case["top_rank_receptor_frame_ca_rmsd_angstrom"] for case in cases]
    best = [case["best_clustered_receptor_frame_ca_rmsd_angstrom"] for case in cases]
    runtimes = [case["runtime_seconds"] for case in cases]

    plt.rcParams.update({"font.size": 9, "axes.titlesize": 11, "axes.labelsize": 9})
    fig, (ax_rmsd, ax_time) = plt.subplots(
        1, 2, figsize=(8.2, 3.5), gridspec_kw={"width_ratios": [1.55, 1]}
    )
    x = np.arange(len(labels))
    width = 0.34
    bars_top = ax_rmsd.bar(
        x - width / 2, top_one, width, label="Top-ranked", color="#2F6B9A"
    )
    bars_best = ax_rmsd.bar(
        x + width / 2,
        best,
        width,
        label="Best of 100",
        color="#E69F00",
        hatch="//",
        edgecolor="#7A5300",
        linewidth=0.6,
    )
    ax_rmsd.axhline(2.0, color="#777777", linestyle="--", linewidth=1)
    ax_rmsd.text(2.48, 2.25, "2 Å guide", ha="right", va="bottom", color="#666666")
    ax_rmsd.set_xticks(x, labels)
    ax_rmsd.set_ylabel("Receptor-frame peptide CA RMSD (Å)")
    ax_rmsd.set_title("Pose recovery and ranking")
    ax_rmsd.legend(frameon=False, loc="upper left")
    ax_rmsd.spines[["top", "right"]].set_visible(False)
    ax_rmsd.bar_label(bars_top, fmt="%.2f", padding=2, fontsize=8)
    ax_rmsd.bar_label(bars_best, fmt="%.2f", padding=2, fontsize=8)

    bars_time = ax_time.bar(x, runtimes, color="#4E9F7A", width=0.58)
    ax_time.set_xticks(x, labels)
    ax_time.set_ylabel("Wall time (s)")
    ax_time.set_title("Direct licensed execution")
    ax_time.spines[["top", "right"]].set_visible(False)
    ax_time.bar_label(bars_time, fmt="%.0f", padding=2, fontsize=8)
    ax_time.set_ylim(0, max(runtimes) * 1.18)

    fig.suptitle("MDockPeP2 public reference redocking", fontsize=12, fontweight="bold")
    fig.text(
        0.5,
        0.01,
        "3/3 exit zero; 2,000 sampling records and 100 clustered poses per complex. "
        "Best-of-100 is an oracle diagnostic, not the operational top-1 result.",
        ha="center",
        va="bottom",
        fontsize=8,
        color="#444444",
    )
    fig.tight_layout(rect=(0, 0.07, 1, 0.92))
    output_stem = run_root / "analysis/mdockpep2-reference-redocking"
    for suffix in ("png", "pdf", "svg"):
        fig.savefig(output_stem.with_suffix(f".{suffix}"), dpi=300, bbox_inches="tight")
    plt.close(fig)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
