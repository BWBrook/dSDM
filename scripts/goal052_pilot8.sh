#!/usr/bin/env bash
# Prepared 48-hour, eight-worker continuation; launch only after the resource decision.
set -eu
repo_root="$(cd "${1:-.}" && pwd)"
run_dir="$repo_root/data/processed/dsdm/goal052-seawfb-dsdm-experiment"
command -v timeout >/dev/null
mkdir -p "$run_dir/logs"
stamp="$(date +%Y%m%dT%H%M%S)-$$"
export CUDA_VISIBLE_DEVICES=""
cd "$repo_root"
# The native runner checks fitting identity/runtime; bind the extra driver too.
uv_bin="$(command -v uv || true)"
if [[ -z "$uv_bin" ]]; then uv_bin="$HOME/.local/bin/uv"; fi
"$uv_bin" run --locked python - <<'PYGATE'
from pathlib import Path
import hashlib, json
receipt = json.loads(Path("metadata/goal052_canary.json").read_text())
assert receipt["qualified_workers"] == 8
assert hashlib.sha256(Path(receipt["qualification_driver"]).read_bytes()).hexdigest() == receipt["qualification_driver_sha256"]
assert hashlib.sha256(Path("metadata/goal052_canary.json").read_bytes()).hexdigest() == "6a67e43792656813ae0c40979161d8e0d6101576b7ea08650a0a1f7ad9f36351"
PYGATE
set +e
timeout --signal=TERM --kill-after=60s 48h \
  env GOAL052_WORKERS=8 GOAL052_DEVICE=cpu \
  bash scripts/goal052_launch.sh "$repo_root"
pilot_status=$?
set -e
printf '%s\n' "$pilot_status" > "$run_dir/logs/pilot8-$stamp.exit.tmp"
mv "$run_dir/logs/pilot8-$stamp.exit.tmp" "$run_dir/logs/pilot8-$stamp.exit"
exit "$pilot_status"
