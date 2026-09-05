#!/usr/bin/env bash

set -u

ROOT="$(cd "${1:-.}" && pwd)"
WORKERS="${GOAL051_WORKERS:-3}"
RUN_DIR="$ROOT/data/processed/dsdm/goal051-seawfb-conventional-benchmark"
LOG="$RUN_DIR/run.log"
EXIT_MARKER="$RUN_DIR/run.exit"

mkdir -p "$RUN_DIR"
rm -f "$EXIT_MARKER" "$EXIT_MARKER.tmp"

(
  cd "$ROOT" || exit 1
  uv run --locked python -m dsdm_phase1.goal051_seawfb_conventional plan --root . &&
    uv run --locked python -m dsdm_phase1.goal051_seawfb_conventional q --root . --workers "$WORKERS" &&
    uv run --locked python -m dsdm_phase1.goal051_seawfb_conventional run --root . --workers "$WORKERS" &&
    uv run --locked python -m dsdm_phase1.goal051_seawfb_conventional aggregate --root . &&
    uv run --locked python -m dsdm_phase1.goal051_seawfb_conventional validate --root . --complete
) >"$LOG" 2>&1
status=$?

printf '%s\n' "$status" >"$EXIT_MARKER.tmp"
mv "$EXIT_MARKER.tmp" "$EXIT_MARKER"
exit "$status"
