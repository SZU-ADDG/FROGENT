#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "usage: $0 JOBS_TSV PHASE" >&2
  exit 2
fi
jobs_tsv=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
phase=$2
run_root=${RUN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}
gpus=(1 3 4 5 6 7)
worker_count=12
mkdir -p "$run_root/state/workers/$phase"
for worker_index in $(seq 0 11); do
  gpu=${gpus[$((worker_index % 6))]}
  state="$run_root/state/workers/$phase/worker-$worker_index"
  mkdir -p "$state"
  printf '%s\n' "$gpu" >"$state/gpu"
  date -Iseconds >"$state/started_at"
  nohup env RUN_ROOT="$run_root" bash "$run_root/scripts/run_job_queue.sh" "$gpu" "$worker_index" "$worker_count" "$jobs_tsv" "$phase" >"$state/stdout.log" 2>"$state/stderr.log" < /dev/null &
  printf '%s\n' "$!" >"$state/pid"
done
