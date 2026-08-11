#!/usr/bin/env python3
import csv
import json
import os
from datetime import datetime
from pathlib import Path

run_root = Path(os.environ["RUN_ROOT"])
source_root = Path("/work/doomx/FROGENT/runtime/evaluation/revision-20260731/gpu-followup-20260802/forge-gauge-matched-budget-prospective-recovery-r06")
rows = []
for queue in sorted((run_root / "protocol").glob("gpu?-jobs.tsv")):
    with queue.open(newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            state = source_root / "state" / "jobs" / row["tag"]
            exit_file = state / "exit_code"
            if not exit_file.is_file():
                raise RuntimeError(f"missing exit code for {row['tag']}")
            rows.append({
                "gpu": int(queue.stem[3]),
                "tag": row["tag"],
                "exit_code": int(exit_file.read_text().strip()),
                "source_state": str(state),
                "source_result": str(source_root / "results" / row["tag"]),
            })

manifest = {
    "schema_version": "frogent-forge-gauge-phase2-scheduling-accelerator-manifest-v1",
    "created_at": datetime.now().astimezone().isoformat(),
    "status": "complete" if all(row["exit_code"] == 0 for row in rows) else "complete_with_failures",
    "scheduling_only": True,
    "source_run": str(source_root),
    "jobs": rows,
    "counts": {
        "total": len(rows),
        "exit_zero": sum(row["exit_code"] == 0 for row in rows),
        "failed": sum(row["exit_code"] != 0 for row in rows),
    },
}
(run_root / "final-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
