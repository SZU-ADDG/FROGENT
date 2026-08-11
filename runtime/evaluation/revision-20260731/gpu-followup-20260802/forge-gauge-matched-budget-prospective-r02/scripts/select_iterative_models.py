#!/usr/bin/env python3
import csv
import json
import statistics
from pathlib import Path

METHOD_ORDER = {"targetdiff": 0, "diffsbdd": 1, "pocket2mol": 2}


def read_rows(path: Path):
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def read_scores(path: Path):
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    return rows, [float(row["QED"]) for row in rows], [float(row["SA_score"]) for row in rows]


def main() -> None:
    run_root = Path(__file__).resolve().parents[1]
    phase1 = read_rows(run_root / "protocol" / "phase1-jobs.tsv")
    round1 = [row for row in phase1 if row["condition"] == "iterative"]
    decisions = []
    phase2 = []
    for pocket in sorted({row["pocket"] for row in round1}):
        for seed in sorted({int(row["seed"]) for row in round1 if row["pocket"] == pocket}):
            candidates = []
            for row in round1:
                if row["pocket"] != pocket or int(row["seed"]) != seed:
                    continue
                tag = row["tag"]
                state_dir = run_root / "state" / "jobs" / tag
                if (state_dir / "exit_code").read_text().strip() != "0":
                    raise SystemExit(f"round-1 job failed: {tag}")
                summary = json.loads((run_root / "results" / tag / "run_summary.json").read_text())
                score_rows, qeds, sas = read_scores(run_root / "results" / tag / "generated_smiles_qed_sa.csv")
                requested = int(summary["requested_samples"])
                valid = int(summary["valid_molecules"])
                unique_ratio = len({item["smiles"] for item in score_rows}) / valid if valid else 0.0
                metrics = {
                    "method": row["method"],
                    "valid_rate": valid / requested,
                    "mean_qed": statistics.fmean(qeds) if qeds else 0.0,
                    "mean_favorable_sa": statistics.fmean(sas) if sas else 0.0,
                    "unique_valid_ratio": unique_ratio,
                }
                metrics["gauge_score"] = (
                    0.50 * metrics["valid_rate"]
                    + 0.30 * metrics["mean_qed"]
                    + 0.20 * metrics["mean_favorable_sa"]
                )
                candidates.append(metrics)
            selected = sorted(
                candidates,
                key=lambda item: (-item["gauge_score"], -item["unique_valid_ratio"], METHOD_ORDER[item["method"]]),
            )[0]
            weakest = min(
                ("valid_rate", "mean_qed", "mean_favorable_sa"),
                key=lambda key: selected[key],
            )
            decisions.append({
                "pocket": pocket,
                "seed": seed,
                "method_metrics": candidates,
                "selected_method": selected["method"],
                "feedback": f"Preserve {selected['method']} and prioritize improvement of {weakest} within the remaining budget.",
                "stop_rule": "One additional round; stop when the matched 1500-attempt budget is exhausted.",
            })
            generation_seed = seed + 10000
            tag = f"iterative-round2-{selected['method']}-{pocket.lower()}-s{generation_seed}-n750-r02"
            phase2.append((len(phase2), "iterative", "round2", selected["method"], pocket, generation_seed, 750, tag))

    (run_root / "gauge-decisions.json").write_text(json.dumps({"decisions": decisions}, indent=2) + "\n")
    output = run_root / "protocol" / "phase2-jobs.tsv"
    with output.open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(("job_index", "condition", "stage", "method", "pocket", "seed", "num_samples", "tag"))
        writer.writerows(phase2)
    if len(phase2) != 15:
        raise SystemExit(f"expected 15 phase-2 jobs, got {len(phase2)}")
    print(output)


if __name__ == "__main__":
    main()
