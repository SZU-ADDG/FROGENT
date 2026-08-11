#!/usr/bin/env python3
import csv
import json
from datetime import datetime
from pathlib import Path


def main() -> None:
    run_root = Path(__file__).resolve().parents[1]
    with (run_root / "protocol" / "retry-jobs.tsv").open(newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    jobs = []
    for row in rows:
        state = run_root / "state" / "jobs" / row["tag"]
        exit_code = int((state / "exit_code").read_text().strip())
        jobs.append({
            **row,
            "job_index": int(row["job_index"]),
            "seed": int(row["seed"]),
            "num_samples": int(row["num_samples"]),
            "batch_size": int((state / "batch_size").read_text().strip()),
            "exit_code": exit_code,
            "gpu": int((state / "gpu").read_text().strip()),
            "started_at": (state / "started_at").read_text().strip(),
            "finished_at": (state / "finished_at").read_text().strip(),
        })
    success = sum(job["exit_code"] == 0 for job in jobs)
    manifest = {
        "status": "complete" if success == len(jobs) else "failed",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "protocol_id": "forge-gauge-matched-budget-prospective-retry-r04",
        "source_protocol_id": "forge-gauge-matched-budget-prospective-r02",
        "expected_jobs": len(jobs),
        "exit_zero_jobs": success,
        "jobs": jobs,
        "amendment": "Two additional terminal failed logical jobs from the frozen 20:25 snapshot rerun sequentially on an exclusive GPU with batch size 8; scientific inputs, seeds and total attempt counts are unchanged."
    }
    output = run_root / "final-manifest.json"
    output.write_text(json.dumps(manifest, indent=2) + "\n")
    print(output)
    if manifest["status"] != "complete":
        raise SystemExit("one or more exact retries failed")


if __name__ == "__main__":
    main()
