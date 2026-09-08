#!/usr/bin/env bash
# Initial Nectar canary and gated production launch; production itself resumes.
set -u

ROOT="$(cd "${1:-.}" && pwd)" || exit 1
RUN_DIR="$ROOT/data/processed/dsdm/goal051-seawfb-conventional-benchmark"
LOG="$RUN_DIR/nectar-execution.log"
EXIT_MARKER="$RUN_DIR/nectar-execution.exit"
mkdir -p "$RUN_DIR" || exit 1
if [[ -e "$LOG" || -e "$EXIT_MARKER" ]]; then
  printf 'Inspect the existing Nectar execution before restarting; see the Goal051 runbook.\n' >&2
  exit 1
fi

export PATH="/usr/local/bin:/usr/bin:/bin"
export UV_CACHE_DIR="/data/codex/cache/uv"
export UV_PYTHON_INSTALL_DIR="/data/codex/cache/uv-python"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export GOAL051_WORKERS=16
umask 077

(
  cd "$ROOT" || exit 1
  date -u '+Nectar execution started: %Y-%m-%dT%H:%M:%SZ'
  git rev-parse HEAD
  uv run --locked python -m dsdm_phase1.goal051_nectar_execution canary-batch --root . &&
    uv run --locked python -m dsdm_phase1.goal051_nectar_execution route --root . --workers "$GOAL051_WORKERS" &&
    uv run --locked python -m dsdm_phase1.goal051_nectar_execution gate --root . --workers "$GOAL051_WORKERS" &&
    bash scripts/goal051_launch.sh .
) >"$LOG" 2>&1
status=$?
printf '%s\n' "$status" >"$EXIT_MARKER.tmp"
mv "$EXIT_MARKER.tmp" "$EXIT_MARKER"
exit "$status"
