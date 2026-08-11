#!/usr/bin/env python3
import csv
import json
from datetime import datetime
from pathlib import Path


SOURCE = Path("/work/doomx/FROGENT/runtime/evaluation/revision-20260731/gpu-followup-20260802/forge-gauge-matched-budget-prospective-r02")


def main() -> None:
    run_root = Path(__file__).resolve().parents[1]
    with (SOURCE / "protocol" / "phase1-jobs.tsv").open(newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    failed = []
    for row in rows:
        if row["method"] != "pocket2mol":
            continue
        exit_file = SOURCE / "state" / "jobs" / row["tag"] / "exit_code"
        if not exit_file.exists():
            raise SystemExit(f"Pocket2Mol lane is not terminal: {row['tag']}")
        if exit_file.read_text().strip() != "0":
            failed.append(row)
    if not failed:
        raise SystemExit("no failed Pocket2Mol jobs to retry")
    output = run_root / "protocol" / "retry-jobs.tsv"
    if output.exists():
        raise SystemExit("refusing to overwrite frozen retry list")
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys(), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for index, row in enumerate(failed):
            writer.writerow({**row, "job_index": index})
    freeze = {
        "frozen_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_protocol": "forge-gauge-matched-budget-prospective-r02",
        "failed_jobs": [row["tag"] for row in failed],
        "count": len(failed),
        "selection_rule": "All and only terminal nonzero-exit Pocket2Mol jobs after both original Pocket2Mol lanes completed.",
    }
    (run_root / "protocol" / "frozen-failure-set.json").write_text(json.dumps(freeze, indent=2) + "\n")
    print(output)


if __name__ == "__main__":
    main()
