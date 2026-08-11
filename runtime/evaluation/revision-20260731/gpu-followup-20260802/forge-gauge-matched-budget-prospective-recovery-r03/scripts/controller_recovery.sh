#!/usr/bin/env bash
set -euo pipefail

run_root=${RUN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}
source_root=/work/doomx/FROGENT/runtime/evaluation/revision-20260731/gpu-followup-20260802/forge-gauge-matched-budget-prospective-r02
retry_root=${RETRY_ROOT:-/work/doomx/FROGENT/runtime/evaluation/revision-20260731/gpu-followup-20260802/forge-gauge-matched-budget-prospective-retry-r01}
python=/work/doomx/anaconda3/envs/mlm/bin/python
state="$run_root/state/controller"
mkdir -p "$state" "$run_root/state/jobs" "$run_root/results" "$run_root/logs"
date -Iseconds >"$state/started_at"

if [ ! -f "$run_root/protocol/phase1-jobs.tsv" ]; then
  cp "$source_root/protocol/phase1-jobs.tsv" "$run_root/protocol/phase1-jobs.tsv"
fi

while true; do
  terminal=0
  failed=0
  while IFS=$'\t' read -r job_index condition stage method pocket seed num_samples tag; do
    [ "$job_index" = job_index ] && continue
    exit_file="$source_root/state/jobs/$tag/exit_code"
    if [ -f "$exit_file" ]; then
      terminal=$((terminal + 1))
      [ "$(cat "$exit_file")" = 0 ] || failed=$((failed + 1))
    fi
  done <"$source_root/protocol/phase1-jobs.tsv"
  printf '%s\tphase1\tterminal=%s\tfailed=%s\n' "$(date -Iseconds)" "$terminal" "$failed" >>"$state/progress.log"
  [ "$terminal" -eq 105 ] && break
  sleep 60
done

while true; do
  if [ -f "$retry_root/final-manifest.json" ] && "$python" - "$retry_root/final-manifest.json" <<'PY'
import json, sys
raise SystemExit(0 if json.load(open(sys.argv[1]))["status"] == "complete" else 1)
PY
  then
    break
  fi
  printf '%s\twaiting-for-exact-retry\n' "$(date -Iseconds)" >>"$state/progress.log"
  sleep 60
done

sources="$run_root/protocol/phase1-job-sources.tsv"
printf 'tag\tsource\n' >"$sources"
while IFS=$'\t' read -r job_index condition stage method pocket seed num_samples tag; do
  [ "$job_index" = job_index ] && continue
  source_state="$source_root/state/jobs/$tag"
  source_result="$source_root/results/$tag"
  source_label=r02
  if [ "$(cat "$source_state/exit_code")" != 0 ]; then
    source_state="$retry_root/state/jobs/$tag"
    source_result="$retry_root/results/$tag"
    source_label=retry-r01
  fi
  [ "$(cat "$source_state/exit_code")" = 0 ] || { echo "no exit-zero source for $tag" >&2; exit 12; }
  [ -d "$source_result" ] || { echo "missing result source for $tag" >&2; exit 13; }
  [ ! -e "$run_root/state/jobs/$tag" ] && [ ! -L "$run_root/state/jobs/$tag" ] || { echo "refusing existing merged state $tag" >&2; exit 14; }
  [ ! -e "$run_root/results/$tag" ] && [ ! -L "$run_root/results/$tag" ] || { echo "refusing existing merged result $tag" >&2; exit 15; }
  ln -s "$source_state" "$run_root/state/jobs/$tag"
  ln -s "$source_result" "$run_root/results/$tag"
  printf '%s\t%s\n' "$tag" "$source_label" >>"$sources"
done <"$run_root/protocol/phase1-jobs.tsv"

date -Iseconds >"$state/merged-phase1-complete-at"
"$python" "$run_root/scripts/select_iterative_models.py" >"$state/select.stdout" 2>"$state/select.stderr"
RUN_ROOT="$run_root" bash "$run_root/scripts/launch_workers.sh" "$run_root/protocol/phase2-jobs.tsv" phase2 >"$state/phase2-launch.stdout" 2>"$state/phase2-launch.stderr"

while true; do
  terminal=0
  failed=0
  while IFS=$'\t' read -r job_index condition stage method pocket seed num_samples tag; do
    [ "$job_index" = job_index ] && continue
    exit_file="$run_root/state/jobs/$tag/exit_code"
    if [ -f "$exit_file" ]; then
      terminal=$((terminal + 1))
      [ "$(cat "$exit_file")" = 0 ] || failed=$((failed + 1))
    fi
  done <"$run_root/protocol/phase2-jobs.tsv"
  printf '%s\tphase2\tterminal=%s\tfailed=%s\n' "$(date -Iseconds)" "$terminal" "$failed" >>"$state/progress.log"
  if [ "$terminal" -eq 15 ]; then
    [ "$failed" -eq 0 ] || exit 20
    break
  fi
  sleep 60
done

"$python" "$run_root/scripts/finalize.py" >"$state/finalize.stdout" 2>"$state/finalize.stderr"
date -Iseconds >"$state/finished_at"
