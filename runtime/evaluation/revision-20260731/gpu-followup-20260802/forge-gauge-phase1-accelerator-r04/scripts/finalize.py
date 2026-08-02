#!/usr/bin/env python3
import csv
import json
from datetime import datetime
from pathlib import Path


def rows(path: Path):
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def main() -> None:
    run_root = Path(__file__).resolve().parents[1]
    source_root = Path("/work/doomx/FROGENT/runtime/evaluation/revision-20260731/gpu-followup-20260802/forge-gauge-matched-budget-prospective-r02")
    jobs = rows(run_root / "protocol" / "targetdiff-jobs.tsv") + rows(run_root / "protocol" / "diffsbdd-jobs.tsv")
    records = []
    for job in jobs:
        state = source_root / "state" / "jobs" / job["tag"]
        exit_code = int((state / "exit_code").read_text().strip())
        records.append(
            {
                **job,
                "job_index": int(job["job_index"]),
                "seed": int(job["seed"]),
                "num_samples": int(job["num_samples"]),
                "exit_code": exit_code,
                "gpu": int((state / "gpu").read_text().strip()),
                "started_at": (state / "started_at").read_text().strip(),
                "finished_at": (state / "finished_at").read_text().strip(),
            }
        )
    exit_zero = sum(record["exit_code"] == 0 for record in records)
    manifest = {
        "status": "complete" if exit_zero == len(records) else "partial_failure",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "protocol_id": "forge-gauge-phase1-accelerator-r04",
        "source_protocol_id": "forge-gauge-matched-budget-prospective-r02",
        "scheduling_only": True,
        "expected_jobs": len(records),
        "terminal_jobs": len(records),
        "exit_zero_jobs": exit_zero,
        "jobs": records,
        "claim_boundary": "Scheduling-only execution of frozen r02 logical jobs; no independent scientific arm."
    }
    output = run_root / "final-manifest.json"
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(output)


if __name__ == "__main__":
    main()
