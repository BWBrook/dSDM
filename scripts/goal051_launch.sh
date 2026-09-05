#!/usr/bin/env bash

set -u

ROOT="$(cd "${1:-.}" 2>/dev/null && pwd)" || {
  printf 'Goal 051 root is not a directory: %s\n' "${1:-.}" >&2
  exit 1
}
WORKERS="${GOAL051_WORKERS:-3}"
RUN_DIR="$ROOT/data/processed/dsdm/goal051-seawfb-conventional-benchmark"
LOG="$RUN_DIR/run.log"
EXIT_MARKER="$RUN_DIR/run.exit"

mkdir -p "$RUN_DIR" || {
  printf 'Unable to create Goal 051 run directory: %s\n' "$RUN_DIR" >&2
  exit 1
}

stamp="$(date +%Y%m%dT%H%M%S%z)"
archive_previous() {
  path="$1"
  if [[ -e "$path" ]]; then
    archive="${path}.previous-${stamp}"
    [[ -e "$archive" ]] && archive="${archive}-$$"
    mv "$path" "$archive" || {
      printf 'Unable to preserve previous run artifact: %s\n' "$path" >&2
      exit 1
    }
  fi
}
archive_previous "$LOG"
archive_previous "$EXIT_MARKER"

case "$(uname -s)" in
  Darwin) PATH="/opt/homebrew/bin:/usr/bin:/bin" ;;
  Linux) PATH="/home/bwbrook/.local/bin:/usr/local/bin:/usr/bin:/bin" ;;
  *) printf 'Unsupported launch host: %s\n' "$(uname -s)" >&2; exit 1 ;;
esac
export PATH

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
