#!/usr/bin/env bash
set -euo pipefail

run_root=${RUN_ROOT:?RUN_ROOT must be an absolute accelerator run root}
source_root=/work/doomx/FROGENT/runtime/evaluation/revision-20260731/gpu-followup-20260802/forge-gauge-matched-budget-prospective-recovery-r06
source_worker="$source_root/scripts/run_job_queue.sh"
state="$run_root/state"
logs="$run_root/logs"
mkdir -p "$state" "$logs"
printf '%s\n' "$$" >"$state/controller.pid"
date -Iseconds >"$state/started_at"

for gpu in 5 6 7; do
  gpu_pids=$(nvidia-smi -i "$gpu" --query-compute-apps=pid --format=csv,noheader,nounits 2>/dev/null | tr -d '[:space:]' || true)
  if [ -n "$gpu_pids" ]; then
    printf '%s\n' "$gpu_pids" >"$state/refused-gpu${gpu}-compute-pids"
    echo "GPU $gpu has compute processes; refusing launch" >&2
    exit 7
  fi
done

for queue in "$run_root"/protocol/gpu?-jobs.tsv; do
  while IFS=$'\t' read -r job_index condition stage method pocket seed num_samples tag; do
    [ "$job_index" = job_index ] && continue
    master_row=$(awk -F '\t' -v wanted="$tag" 'NR > 1 && $8 == wanted {print; count++} END {if (count != 1) exit 9}' "$source_root/protocol/phase2-jobs.tsv")
    selected_row=$(printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s' "$job_index" "$condition" "$stage" "$method" "$pocket" "$seed" "$num_samples" "$tag")
    [ "$master_row" = "$selected_row" ] || { echo "selected row differs from frozen master: $tag" >&2; exit 10; }
    [ ! -e "$source_root/state/jobs/$tag" ] || { echo "refusing pre-existing source state: $tag" >&2; exit 11; }
  done <"$queue"
done
date -Iseconds >"$state/preflight-complete-at"

worker_pids=()
for gpu in 5 6 7; do
  queue="$run_root/protocol/gpu${gpu}-jobs.tsv"
  RUN_ROOT="$source_root" bash "$source_worker" "$gpu" 0 1 "$queue" phase2-accelerator-r01 \
    >"$logs/gpu${gpu}-worker.stdout" 2>"$logs/gpu${gpu}-worker.stderr" &
  pid=$!
  worker_pids+=("$pid")
  printf '%s\n' "$pid" >"$state/gpu${gpu}-worker.pid"
done

failed_workers=0
for index in 0 1 2; do
  gpu=$((index + 5))
  set +e
  wait "${worker_pids[$index]}"
  code=$?
  set -e
  printf '%s\n' "$code" >"$state/gpu${gpu}-worker.exit"
  [ "$code" -eq 0 ] || failed_workers=$((failed_workers + 1))
done
[ "$failed_workers" -eq 0 ] || exit 20

RUN_ROOT="$run_root" /work/doomx/anaconda3/envs/mlm/bin/python "$run_root/scripts/finalize.py" \
  >"$state/finalize.stdout" 2>"$state/finalize.stderr"
date -Iseconds >"$state/finished_at"
