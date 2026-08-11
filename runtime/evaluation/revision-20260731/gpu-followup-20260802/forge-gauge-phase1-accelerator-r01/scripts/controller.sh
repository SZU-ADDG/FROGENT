#!/usr/bin/env bash
set -euo pipefail

run_root=${RUN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}
source_root=/work/doomx/FROGENT/runtime/evaluation/revision-20260731/gpu-followup-20260802/forge-gauge-matched-budget-prospective-r02
source_worker="$source_root/scripts/run_job_queue.sh"
state="$run_root/state"
logs="$run_root/logs"
mkdir -p "$state" "$logs"
date -Iseconds >"$state/started_at"

for queue in "$run_root/protocol/targetdiff-jobs.tsv" "$run_root/protocol/diffsbdd-jobs.tsv"; do
  while IFS=$'\t' read -r job_index condition stage method pocket seed num_samples tag; do
    [ "$job_index" = job_index ] && continue
    if [ -e "$source_root/state/jobs/$tag" ]; then
      echo "refusing pre-existing source state for selected accelerator tag: $tag" >&2
      exit 11
    fi
  done <"$queue"
done
date -Iseconds >"$state/preflight-complete-at"

bash "$source_worker" 6 0 1 "$run_root/protocol/targetdiff-jobs.tsv" phase1-accelerator-targetdiff \
  >"$logs/targetdiff-worker.stdout" 2>"$logs/targetdiff-worker.stderr" &
targetdiff_pid=$!
printf '%s\n' "$targetdiff_pid" >"$state/targetdiff-worker.pid"

bash "$source_worker" 6 0 1 "$run_root/protocol/diffsbdd-jobs.tsv" phase1-accelerator-diffsbdd \
  >"$logs/diffsbdd-worker.stdout" 2>"$logs/diffsbdd-worker.stderr" &
diffsbdd_pid=$!
printf '%s\n' "$diffsbdd_pid" >"$state/diffsbdd-worker.pid"

set +e
wait "$targetdiff_pid"
targetdiff_code=$?
wait "$diffsbdd_pid"
diffsbdd_code=$?
set -e
printf '%s\n' "$targetdiff_code" >"$state/targetdiff-worker.exit"
printf '%s\n' "$diffsbdd_code" >"$state/diffsbdd-worker.exit"
[ "$targetdiff_code" -eq 0 ] && [ "$diffsbdd_code" -eq 0 ] || exit 20

while true; do
  terminal=0
  failed=0
  for queue in "$run_root/protocol/targetdiff-jobs.tsv" "$run_root/protocol/diffsbdd-jobs.tsv"; do
    while IFS=$'\t' read -r job_index condition stage method pocket seed num_samples tag; do
      [ "$job_index" = job_index ] && continue
      exit_file="$source_root/state/jobs/$tag/exit_code"
      if [ -f "$exit_file" ]; then
        terminal=$((terminal + 1))
        [ "$(cat "$exit_file")" = 0 ] || failed=$((failed + 1))
      fi
    done <"$queue"
  done
  printf '%s\tterminal=%s\tfailed=%s\n' "$(date -Iseconds)" "$terminal" "$failed" >>"$state/progress.log"
  [ "$terminal" -eq 8 ] && break
  sleep 30
done

/work/doomx/anaconda3/envs/mlm/bin/python "$run_root/scripts/finalize.py" \
  >"$state/finalize.stdout" 2>"$state/finalize.stderr"
date -Iseconds >"$state/finished_at"
