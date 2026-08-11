#!/usr/bin/env python3
import csv
import json
from pathlib import Path


BASE = Path("/work/doomx/FROGENT/runtime/evaluation/revision-20260731/gpu-followup-20260802")
SOURCE = BASE / "forge-gauge-matched-budget-prospective-r02"


def completed_retry_roots() -> dict[Path, set[str]]:
    roots = {}
    for root in sorted(BASE.glob("forge-gauge-matched-budget-prospective-retry-r*")):
        manifest_path = root / "final-manifest.json"
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if manifest.get("status") == "complete":
            roots[root] = {
                str(job["tag"])
                for job in manifest.get("jobs", [])
                if int(job.get("exit_code", 1)) == 0
            }
    return roots


def main() -> None:
    run_root = Path(__file__).resolve().parents[1]
    with (SOURCE / "protocol" / "phase1-jobs.tsv").open(newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    retries = completed_retry_roots()
    selected = []
    missing = []
    for row in rows:
        tag = row["tag"]
        source_state = SOURCE / "state" / "jobs" / tag
        source_result = SOURCE / "results" / tag
        source_exit_path = source_state / "exit_code"
        if not source_exit_path.is_file():
            raise SystemExit(f"source phase is not terminal: {tag}")
        source_exit = source_exit_path.read_text().strip()
        if source_exit == "0":
            candidates = [("r02", source_state, source_result)]
        else:
            candidates = []
            for retry, manifest_tags in retries.items():
                if tag not in manifest_tags:
                    continue
                retry_state = retry / "state" / "jobs" / tag
                retry_result = retry / "results" / tag
                retry_exit = retry_state / "exit_code"
                if retry_exit.is_file() and retry_exit.read_text().strip() == "0" and retry_result.is_dir():
                    candidates.append((retry.name, retry_state, retry_result))
        if not candidates:
            missing.append(tag)
            continue
        label, state_path, result_path = candidates[0]
        if not result_path.is_dir():
            missing.append(tag)
            continue
        selected.append({
            "tag": tag,
            "source": label,
            "state_path": str(state_path),
            "result_path": str(result_path),
            "candidate_count": len(candidates),
        })
    if missing:
        print(json.dumps({"status": "waiting", "missing": missing}, sort_keys=True))
        raise SystemExit(2)
    output = run_root / "protocol" / "phase1-job-sources.tsv"
    roots_output = run_root / "protocol" / "retry-root-manifests.json"
    if output.exists() or roots_output.exists():
        raise SystemExit("refusing to overwrite frozen recovery source map")
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=selected[0].keys(), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(selected)
    roots_output.write_text(json.dumps({
        "complete_retry_roots": [str(root) for root in retries],
        "selected_retry_roots": sorted({row["source"] for row in selected if row["source"] != "r02"}),
        "source_jobs": len(selected),
    }, indent=2) + "\n")
    print(json.dumps({"status": "complete", "source_jobs": len(selected)}, sort_keys=True))


if __name__ == "__main__":
    main()
