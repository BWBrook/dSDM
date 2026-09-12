#!/usr/bin/env bash
# Run inside detached tmux session dsdm-goal052-dsdm; all leaves are resumable.
set -eu
repo_root="$(cd "${1:-.}" && pwd)"
run_dir="$repo_root/data/processed/dsdm/goal052-seawfb-dsdm-experiment"
workers="${GOAL052_WORKERS:-1}"
device="${GOAL052_DEVICE:-cpu}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
uv_bin="$(command -v uv || true)"
if [[ -z "$uv_bin" ]]; then uv_bin="$HOME/.local/bin/uv"; fi
[[ -x "$uv_bin" ]] || { printf 'uv is unavailable\n' >&2; exit 1; }
mkdir -p "$run_dir/logs"
stamp="$(date +%Y%m%dT%H%M%S)-$$"
log_file="$run_dir/logs/run-$stamp.log"
cd "$repo_root"
set +e
"$uv_bin" run --locked python -m dsdm_phase1.goal052_seawfb_dsdm run --root . --workers "$workers" --device "$device" >"$log_file" 2>&1
run_status=$?
set -e
printf '%s\n' "$run_status" >"$run_dir/logs/run-$stamp.exit.tmp"
mv "$run_dir/logs/run-$stamp.exit.tmp" "$run_dir/logs/run-$stamp.exit"
exit "$run_status"
