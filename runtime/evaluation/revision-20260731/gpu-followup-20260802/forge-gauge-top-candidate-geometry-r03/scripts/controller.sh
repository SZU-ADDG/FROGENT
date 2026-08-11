#!/usr/bin/env bash
set -euo pipefail

run_root=${RUN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}
source_root=/work/doomx/FROGENT/runtime/evaluation/revision-20260731/gpu-followup-20260802/forge-gauge-matched-budget-prospective-recovery-r06
input_root=/work/doomx/FROGENT/runtime/evaluation/revision-20260731/gpu-final/cbgbench/inputs
python=/work/doomx/anaconda3/envs/mlm/bin/python
workspace=/work/doomx/FROGENT/runtime/evaluation/revision-20260731/gpu-final/cbgbench/workspace
packages=/work/doomx/FROGENT/runtime/evaluation/revision-20260731/gpu-final/cbgbench/python-packages
state="$run_root/state"
mkdir -p "$state"
date -Iseconds >"$state/started_at"

while true; do
  if [ -f "$source_root/final-manifest.json" ]; then
    set +e
    gate=$(
      "$python" - "$source_root/final-manifest.json" <<'PY'
import json
import sys
data = json.load(open(sys.argv[1]))
ok = (
    data.get("status") == "complete"
    and data.get("expected_jobs") == 120
    and data.get("exit_zero_jobs") == 120
    and data.get("paired_cells_per_condition") == 15
)
print("ready" if ok else "not-ready")
raise SystemExit(0 if ok else 2)
PY
    )
    gate_code=$?
    set -e
    printf '%s\tsource-gate\t%s\n' "$(date -Iseconds)" "$gate" >>"$state/progress.log"
    [ "$gate_code" -eq 0 ] && break
  else
    printf '%s\twaiting-for-source-final\n' "$(date -Iseconds)" >>"$state/progress.log"
  fi
  sleep 60
done

export PYTHONPATH="$packages:$workspace"
export RDBASE=/work/doomx/anaconda3/envs/mlm/lib/python3.10/site-packages/rdkit
export PYTHONUNBUFFERED=1
"$python" "$run_root/scripts/analyze.py" \
  --source-root "$source_root" \
  --input-root "$input_root" \
  --protocol "$run_root/protocol/preregistration.json" \
  --output-root "$run_root/output" \
  --workers 24 \
  >"$state/analysis.stdout" 2>"$state/analysis.stderr"
date -Iseconds >"$state/finished_at"
