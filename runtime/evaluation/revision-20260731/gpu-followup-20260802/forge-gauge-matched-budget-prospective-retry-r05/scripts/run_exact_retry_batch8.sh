#!/usr/bin/env bash
set -euo pipefail

[ "$#" -eq 1 ] || { echo "usage: $0 PHYSICAL_GPU" >&2; exit 2; }
gpu=$1
base_root=/work/doomx/FROGENT/runtime/evaluation/revision-20260731/gpu-final/cbgbench
source_root=/work/doomx/FROGENT/runtime/evaluation/revision-20260731/gpu-followup-20260802/forge-gauge-matched-budget-prospective-r02
run_root=${RUN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}
workspace="$base_root/workspace"
python=/work/doomx/anaconda3/envs/mlm/bin/python
packages="$base_root/python-packages"
jobs_tsv="$run_root/protocol/retry-jobs.tsv"
mkdir -p "$run_root/state/jobs" "$run_root/results" "$run_root/logs"
cd "$workspace"
export CUDA_VISIBLE_DEVICES="$gpu"
export PYTHONPATH="$packages:$workspace"
export RDBASE=/work/doomx/anaconda3/envs/mlm/lib/python3.10/site-packages/rdkit
export BABEL_LIBDIR="$packages/openbabel/lib/openbabel/3.1.0"
export BABEL_DATADIR="$packages/openbabel/share/openbabel/3.1.0"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export PYTHONUNBUFFERED=1

tail -n +2 "$jobs_tsv" | while IFS=$'\t' read -r job_index condition stage method pocket seed num_samples tag; do
  source_exit="$source_root/state/jobs/$tag/exit_code"
  [ -f "$source_exit" ] && [ "$(cat "$source_exit")" != 0 ] || { echo "refusing nonfailed source job: $tag" >&2; exit 5; }
  state_dir="$run_root/state/jobs/$tag"
  mkdir -p "$state_dir"
  [ ! -e "$state_dir/pid" ] && [ ! -e "$state_dir/exit_code" ] || { echo "refusing existing retry state: $tag" >&2; exit 6; }
  [ "$(df -Pk "$run_root" | awk 'NR==2 {print $4}')" -ge 104857600 ] || { echo "less than 100 GiB free" >&2; exit 8; }
  printf '%s\n' "$condition" >"$state_dir/condition"
  printf '%s\n' "$stage" >"$state_dir/stage"
  printf '%s\n' "$method" >"$state_dir/method"
  printf '%s\n' "$pocket" >"$state_dir/pocket"
  printf '%s\n' "$seed" >"$state_dir/seed"
  printf '%s\n' "$num_samples" >"$state_dir/num_samples"
  printf '%s\n' "$gpu" >"$state_dir/gpu"
  printf '%s\n' "$tag" >"$state_dir/retry_of"
  printf '%s\n' 8 >"$state_dir/batch_size"
  date -Iseconds >"$state_dir/started_at"
  set +e
  "$python" case_gen.py --method "$method" --protein_path "$base_root/inputs/$pocket/receptor-selected.pdb" --ligand_path "$base_root/inputs/$pocket/ligand-ph74.sdf" --use_ref_ligand_for_pocket --pocket_radius 10 --out_root "$run_root/results" --log_root "$run_root/logs" --tag "$tag" --num_samples "$num_samples" --batch_size 8 --device cuda:0 --seed "$seed" --threshold -1 --threshold_ratio 0.8 >"$state_dir/stdout.log" 2>"$state_dir/stderr.log" &
  job_pid=$!
  printf '%s\n' "$job_pid" >"$state_dir/pid"
  (
    while kill -0 "$job_pid" 2>/dev/null; do
      printf '%s,%s,' "$(date -Iseconds)" "$tag"
      nvidia-smi --query-gpu=index,utilization.gpu,memory.used,memory.total,power.draw --format=csv,noheader,nounits -i "$gpu"
      sleep 10
    done
  ) >"$state_dir/telemetry.csv" 2>&1 &
  telemetry_pid=$!
  wait "$job_pid"
  exit_code=$?
  wait "$telemetry_pid" 2>/dev/null
  set -e
  printf '%s\n' "$exit_code" >"$state_dir/exit_code"
  date -Iseconds >"$state_dir/finished_at"
  printf 'Finished %s with exit %s\n' "$tag" "$exit_code"
done
RUN_ROOT="$run_root" "$python" "$run_root/scripts/finalize_retry.py"
