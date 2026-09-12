#!/usr/bin/env bash
# Prepared 24-hour, two-worker pilot; launch only after the resource decision.
set -eu
repo_root="$(cd "${1:-.}" && pwd)"
run_dir="$repo_root/data/processed/dsdm/goal052-seawfb-dsdm-experiment"
command -v timeout >/dev/null
mkdir -p "$run_dir/logs"
stamp="$(date +%Y%m%dT%H%M%S)-$$"
export CUDA_VISIBLE_DEVICES=""
cd "$repo_root"
set +e
timeout --signal=TERM --kill-after=60s 24h \
  env GOAL052_WORKERS=2 GOAL052_DEVICE=cpu \
  bash scripts/goal052_launch.sh "$repo_root"
pilot_status=$?
set -e
printf '%s\n' "$pilot_status" > "$run_dir/logs/pilot-$stamp.exit.tmp"
mv "$run_dir/logs/pilot-$stamp.exit.tmp" "$run_dir/logs/pilot-$stamp.exit"
exit "$pilot_status"
