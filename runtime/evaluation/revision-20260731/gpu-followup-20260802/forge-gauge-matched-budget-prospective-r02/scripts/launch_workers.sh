#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "usage: $0 JOBS_TSV PHASE" >&2
  exit 2
fi

jobs_tsv=$1
phase=$2
case "$jobs_tsv" in
  /*) ;;
  *) jobs_tsv="$(cd "$(dirname "$jobs_tsv")" && pwd)/$(basename "$jobs_tsv")" ;;
esac
[ -f "$jobs_tsv" ] || { echo "jobs TSV does not exist: $jobs_tsv" >&2; exit 2; }
run_root=/work/doomx/FROGENT/runtime/evaluation/revision-20260731/gpu-followup-20260802/forge-gauge-matched-budget-prospective-r02
worker="$run_root/scripts/run_job_queue.sh"
worker_count=12
gpus=(1 3 4 5 6 7)
launcher_state="$run_root/state/workers/$phase"

mkdir -p "$launcher_state"
if [ "$(df -Pk "$run_root" | awk 'NR==2 {print $4}')" -lt 104857600 ]; then
  echo "Refusing launch: less than 100 GiB is free." >&2
  exit 3
fi

for worker_index in $(seq 0 11); do
  gpu=${gpus[$((worker_index % 6))]}
  state_dir="$launcher_state/worker-$worker_index"
  mkdir -p "$state_dir"
  if [ -f "$state_dir/pid" ]; then
    old_pid=$(cat "$state_dir/pid")
    if kill -0 "$old_pid" 2>/dev/null; then
      echo "Worker $worker_index already active at PID $old_pid"
      continue
    fi
    echo "Refusing to relaunch recorded worker $worker_index" >&2
    exit 4
  fi
  free_mib=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits -i "$gpu")
  if [ "$free_mib" -lt 15000 ]; then
    echo "GPU $gpu has only ${free_mib} MiB free; refusing worker $worker_index" >&2
    exit 5
  fi
  nohup "$worker" "$gpu" "$worker_index" "$worker_count" "$jobs_tsv" "$phase" \
    >"$state_dir/stdout.log" 2>"$state_dir/stderr.log" </dev/null &
  pid=$!
  printf '%s\n' "$pid" >"$state_dir/pid"
  printf '%s\n' "$gpu" >"$state_dir/gpu"
  date -Iseconds >"$state_dir/started_at"
  echo "Started $phase worker $worker_index on GPU $gpu at PID $pid"
done
