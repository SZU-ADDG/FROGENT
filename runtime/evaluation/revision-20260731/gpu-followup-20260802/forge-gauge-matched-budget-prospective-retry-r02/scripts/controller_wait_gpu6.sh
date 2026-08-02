#!/usr/bin/env bash
set -euo pipefail

run_root=/work/doomx/FROGENT/runtime/evaluation/revision-20260731/gpu-followup-20260802/forge-gauge-matched-budget-prospective-retry-r02
source_root=/work/doomx/FROGENT/runtime/evaluation/revision-20260731/gpu-followup-20260802/forge-gauge-matched-budget-prospective-r02
python=/work/doomx/anaconda3/envs/mlm/bin/python
state="$run_root/state/controller"
mkdir -p "$state"
date -Iseconds >"$state/started_at"

for worker_index in 4 10; do
  worker_pid=$(cat "$source_root/state/workers/phase1/worker-$worker_index/pid")
  while kill -0 "$worker_pid" 2>/dev/null; do
    printf '%s\twaiting-for-pocket2mol-worker-%s\t%s\n' "$(date -Iseconds)" "$worker_index" "$worker_pid" >>"$state/progress.log"
    sleep 30
  done
done
date -Iseconds >"$state/source-pocket2mol-workers-finished-at"

"$python" "$run_root/scripts/freeze_failed_jobs.py" >"$state/freeze.stdout" 2>"$state/freeze.stderr"
date -Iseconds >"$state/failure-set-frozen-at"

while true; do
  gpu_pids=$(nvidia-smi -i 6 --query-compute-apps=pid --format=csv,noheader,nounits 2>/dev/null | tr -d '[:space:]' || true)
  if [ -z "$gpu_pids" ]; then
    break
  fi
  printf '%s\twaiting-for-exclusive-gpu-6\t%s\n' "$(date -Iseconds)" "$gpu_pids" >>"$state/progress.log"
  sleep 30
done
date -Iseconds >"$state/exclusive-gpu-acquired-at"
bash "$run_root/scripts/run_exact_retry_batch8.sh" 6 >"$state/retry.stdout" 2>"$state/retry.stderr"
date -Iseconds >"$state/finished_at"
