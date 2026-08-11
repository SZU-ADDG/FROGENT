#!/usr/bin/env bash
set -euo pipefail

run_root=/work/doomx/FROGENT/runtime/evaluation/revision-20260731/gpu-followup-20260802/forge-gauge-matched-budget-prospective-retry-r01
source_root=/work/doomx/FROGENT/runtime/evaluation/revision-20260731/gpu-followup-20260802/forge-gauge-matched-budget-prospective-r02
state="$run_root/state/controller"
mkdir -p "$state"
date -Iseconds >"$state/started_at"

worker_pid=$(cat "$source_root/state/workers/phase1/worker-4/pid")
while kill -0 "$worker_pid" 2>/dev/null; do
  printf '%s\twaiting-for-r02-worker-4\t%s\n' "$(date -Iseconds)" "$worker_pid" >>"$state/progress.log"
  sleep 30
done
date -Iseconds >"$state/source-worker-finished-at"

while true; do
  gpu_pids=$(nvidia-smi -i 6 --query-compute-apps=pid --format=csv,noheader,nounits 2>/dev/null | tr -d '[:space:]' || true)
  if [ -z "$gpu_pids" ]; then
    break
  fi
  printf '%s\twaiting-for-exclusive-gpu-6\t%s\n' "$(date -Iseconds)" "$gpu_pids" >>"$state/progress.log"
  sleep 30
done
date -Iseconds >"$state/exclusive-gpu-acquired-at"

bash "$run_root/scripts/run_exact_retry.sh" 6 >"$state/retry.stdout" 2>"$state/retry.stderr"
date -Iseconds >"$state/finished_at"
