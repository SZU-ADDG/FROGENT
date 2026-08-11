#!/usr/bin/env bash
set -euo pipefail

run_root=${RUN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}
state="$run_root/state/controller"
mkdir -p "$state"
date -Iseconds >"$state/started_at"

gpu_pids=$(nvidia-smi -i 6 --query-compute-apps=pid --format=csv,noheader,nounits 2>/dev/null | tr -d '[:space:]' || true)
if [ -n "$gpu_pids" ]; then
  printf '%s\n' "$gpu_pids" >"$state/refused-compute-pids"
  echo "GPU 6 has compute processes; refusing launch" >&2
  exit 7
fi
date -Iseconds >"$state/exclusive-gpu-acquired-at"
RUN_ROOT="$run_root" bash "$run_root/scripts/run_exact_retry_batch8.sh" 6 >"$state/retry.stdout" 2>"$state/retry.stderr"
date -Iseconds >"$state/finished_at"
