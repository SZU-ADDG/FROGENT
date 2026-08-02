#!/usr/bin/env bash
set -euo pipefail

run_root=/work/doomx/FROGENT/runtime/evaluation/revision-20260731/gpu-followup-20260802/forge-gauge-matched-budget-prospective-r02
python=/work/doomx/anaconda3/envs/mlm/bin/python
state="$run_root/state/controller"
mkdir -p "$state"
date -Iseconds >"$state/append-only-controller-started-at"

wait_for_phase() {
  local jobs_tsv=$1
  local expected=$2
  local label=$3
  while true; do
    terminal=0
    failed=0
    while IFS=$'\t' read -r job_index condition stage method pocket seed num_samples tag; do
      [ "$job_index" = "job_index" ] && continue
      exit_file="$run_root/state/jobs/$tag/exit_code"
      if [ -f "$exit_file" ]; then
        terminal=$((terminal + 1))
        [ "$(cat "$exit_file")" = "0" ] || failed=$((failed + 1))
      fi
    done <"$jobs_tsv"
    printf '%s\t%s\t%s\t%s\n' "$(date -Iseconds)" "$label" "$terminal" "$failed" >>"$state/progress.log"
    if [ "$terminal" -eq "$expected" ]; then
      if [ "$failed" -ne 0 ]; then
        printf '%s\n' "$failed" >"$state/${label}-failed-jobs"
        exit 10
      fi
      return
    fi
    sleep 60
  done
}

phase1="$run_root/protocol/phase1-jobs.tsv"
wait_for_phase "$phase1" 105 phase1
date -Iseconds >"$state/phase1-complete-at"
"$python" "$run_root/scripts/select_iterative_models.py" >"$state/select.stdout" 2>"$state/select.stderr"
phase2="$run_root/protocol/phase2-jobs.tsv"
"$run_root/scripts/launch_workers.sh" "$phase2" phase2 >"$state/phase2-launch.stdout" 2>"$state/phase2-launch.stderr"
wait_for_phase "$phase2" 15 phase2
date -Iseconds >"$state/phase2-complete-at"
"$python" "$run_root/scripts/finalize.py" >"$state/finalize.stdout" 2>"$state/finalize.stderr"
date -Iseconds >"$state/finished_at"
