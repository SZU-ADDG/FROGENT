#!/usr/bin/env python3
import csv
from pathlib import Path

POCKETS = ("1IEP", "2HYY", "3CS9", "4WA9", "1M17")
SEEDS = (83, 97, 109)
METHODS = ("targetdiff", "pocket2mol", "diffsbdd")


def main() -> None:
    output = Path(__file__).resolve().parents[1] / "protocol" / "phase1-jobs.tsv"
    rows = []
    index = 0
    for pocket in POCKETS:
        for seed in SEEDS:
            tag = f"fixed-best-targetdiff-{pocket.lower()}-s{seed}-n1500-r02"
            rows.append((index, "fixed_best", "single", "targetdiff", pocket, seed, 1500, tag))
            index += 1
    for condition, stage, samples in (
        ("single_pass", "single", 500),
        ("iterative", "round1", 250),
    ):
        for pocket in POCKETS:
            for seed in SEEDS:
                for method in METHODS:
                    tag = (
                        f"{condition.replace('_', '-')}-{stage}-{method}-"
                        f"{pocket.lower()}-s{seed}-n{samples}-r02"
                    )
                    rows.append((index, condition, stage, method, pocket, seed, samples, tag))
                    index += 1
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(("job_index", "condition", "stage", "method", "pocket", "seed", "num_samples", "tag"))
        writer.writerows(rows)
    if len(rows) != 105:
        raise SystemExit(f"expected 105 phase-1 jobs, got {len(rows)}")
    print(output)


if __name__ == "__main__":
    main()
