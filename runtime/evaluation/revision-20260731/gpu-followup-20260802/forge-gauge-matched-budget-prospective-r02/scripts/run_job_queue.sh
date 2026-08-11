#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 5 ]; then
  echo "usage: $0 GPU WORKER_INDEX WORKER_COUNT JOBS_TSV PHASE" >&2
  exit 2
fi

gpu=$1
worker_index=$2
worker_count=$3
jobs_tsv=$4
phase=$5
case "$jobs_tsv" in
  /*) ;;
  *) echo "jobs TSV must be an absolute path: $jobs_tsv" >&2; exit 2 ;;
esac
[ -f "$jobs_tsv" ] || { echo "jobs TSV does not exist: $jobs_tsv" >&2; exit 2; }
base_root=/work/doomx/FROGENT/runtime/evaluation/revision-20260731/gpu-final/cbgbench
run_root=/work/doomx/FROGENT/runtime/evaluation/revision-20260731/gpu-followup-20260802/forge-gauge-matched-budget-prospective-r02
workspace="$base_root/workspace"
python=/work/doomx/anaconda3/envs/mlm/bin/python
packages="$base_root/python-packages"
state_root="$run_root/state/jobs"
result_root="$run_root/results"
log_root="$run_root/logs"

mkdir -p "$state_root" "$result_root" "$log_root"
cd "$workspace"
export CUDA_VISIBLE_DEVICES="$gpu"
export PYTHONPATH="$packages:$workspace"
export RDBASE=/work/doomx/anaconda3/envs/mlm/lib/python3.10/site-packages/rdkit
export BABEL_LIBDIR="$packages/openbabel/lib/openbabel/3.1.0"
export BABEL_DATADIR="$packages/openbabel/share/openbabel/3.1.0"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export PYTHONUNBUFFERED=1

tail -n +2 "$jobs_tsv" | while IFS=$'\t' read -r job_index condition stage method pocket seed num_samples tag; do
  if [ $((job_index % worker_count)) -ne "$worker_index" ]; then
    continue
  fi
  state_dir="$state_root/$tag"
  mkdir -p "$state_dir"
  if [ -e "$state_dir/exit_code" ]; then
    echo "Skipping terminal job $tag"
    continue
  fi
  if [ -e "$state_dir/pid" ]; then
    previous_pid=$(cat "$state_dir/pid")
    if kill -0 "$previous_pid" 2>/dev/null; then
      echo "Skipping active job $tag at PID $previous_pid"
      continue
    fi
    echo "Refusing to overwrite nonterminal state for $tag" >&2
    exit 4
  fi
  if [ "$(df -Pk "$run_root" | awk 'NR==2 {print $4}')" -lt 104857600 ]; then
    echo "Stopping worker: less than 100 GiB is free." >&2
    exit 3
  fi

  {
    printf '%q ' "$python" case_gen.py
    printf '%q ' \
      --method "$method" \
      --protein_path "$base_root/inputs/$pocket/receptor-selected.pdb" \
      --ligand_path "$base_root/inputs/$pocket/ligand-ph74.sdf" \
      --use_ref_ligand_for_pocket \
      --pocket_radius 10 \
      --out_root "$result_root" \
      --log_root "$log_root" \
      --tag "$tag" \
      --num_samples "$num_samples" \
      --batch_size 32 \
      --device cuda:0 \
      --seed "$seed" \
      --threshold -1 \
      --threshold_ratio 0.8
    printf '\n'
  } >"$state_dir/command.txt"
  printf '%s\n' "$condition" >"$state_dir/condition"
  printf '%s\n' "$stage" >"$state_dir/stage"
  printf '%s\n' "$gpu" >"$state_dir/gpu"
  printf '%s\n' "$worker_index" >"$state_dir/worker_index"
  printf '%s\n' "$phase" >"$state_dir/phase"
  date -Iseconds >"$state_dir/started_at"

  set +e
  "$python" case_gen.py \
    --method "$method" \
    --protein_path "$base_root/inputs/$pocket/receptor-selected.pdb" \
    --ligand_path "$base_root/inputs/$pocket/ligand-ph74.sdf" \
    --use_ref_ligand_for_pocket \
    --pocket_radius 10 \
    --out_root "$result_root" \
    --log_root "$log_root" \
    --tag "$tag" \
    --num_samples "$num_samples" \
    --batch_size 32 \
    --device cuda:0 \
    --seed "$seed" \
    --threshold -1 \
    --threshold_ratio 0.8 \
    >"$state_dir/stdout.log" 2>"$state_dir/stderr.log" &
  job_pid=$!
  printf '%s\n' "$job_pid" >"$state_dir/pid"
  (
    while kill -0 "$job_pid" 2>/dev/null; do
      printf '%s,%s,' "$(date -Iseconds)" "$tag"
      nvidia-smi --query-gpu=index,utilization.gpu,memory.used,memory.total,power.draw \
        --format=csv,noheader,nounits -i "$gpu"
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
  echo "Finished $tag on physical GPU $gpu with exit $exit_code"
done
