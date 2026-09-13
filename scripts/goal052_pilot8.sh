#!/usr/bin/env bash
# Approved 48-hour, eight-worker continuation; review evidence at the cap.
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
GOAL052_LAUNCH_STAMP="$stamp" "$uv_bin" run --locked python - <<'PYGATE'
from pathlib import Path
import hashlib, json, os
from datetime import datetime, timedelta, timezone
receipt = json.loads(Path("metadata/goal052_canary.json").read_text())
assert receipt["qualified_workers"] == 8
assert hashlib.sha256(Path(receipt["qualification_driver"]).read_bytes()).hexdigest() == receipt["qualification_driver_sha256"]
assert hashlib.sha256(Path("metadata/goal052_canary.json").read_bytes()).hexdigest() == "6a67e43792656813ae0c40979161d8e0d6101576b7ea08650a0a1f7ad9f36351"
started = datetime.now(timezone.utc)
launch = {
    "started_utc": started.isoformat(),
    "nominal_deadline_utc": (started + timedelta(hours=48)).isoformat(),
    "workers": 8, "device": "cpu", "cap_hours": 48,
    "worker_hour_cap": 384, "termination_allowance_seconds": 60,
    "session": "dsdm-goal052-pilot8", "wrapper_pid": os.getppid(),
    "pilot_exit": "logs/pilot8-" + os.environ["GOAL052_LAUNCH_STAMP"] + ".exit",
    "wrapper_sha256": hashlib.sha256(Path("scripts/goal052_pilot8.sh").read_bytes()).hexdigest(),
    "canary_sha256": hashlib.sha256(Path("metadata/goal052_canary.json").read_bytes()).hexdigest(),
    "profile_sha256": hashlib.sha256(Path("metadata/goal052_full_epoch_profile.json").read_bytes()).hexdigest(),
    "identity": receipt["identity"],
    "authorization": "Barry approved launch on 13 September 2026 and granted standing authority to allocate compute resources. Review this bounded run before choosing subsequent allocations.",
}
launch_path = Path("data/processed/dsdm/goal052-seawfb-dsdm-experiment/pilot8-launch.json")
with launch_path.open("x") as stream:
    json.dump(launch, stream, indent=2)
    stream.write("\n")
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
