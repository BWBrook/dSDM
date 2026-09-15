#!/usr/bin/env bash
# Seven-day, 24-worker allocation; daily reviews may stop it earlier.
set -eu
repo_root="$(cd "${1:-.}" && pwd)"
cd "$repo_root"
run_dir="$repo_root/data/processed/dsdm/goal052-seawfb-dsdm-experiment"
command -v timeout >/dev/null
export CUDA_VISIBLE_DEVICES=""
stamp="$(date +%Y%m%dT%H%M%S)-$$"
uv_bin="$(command -v uv || true)"
if [[ -z "$uv_bin" ]]; then uv_bin="$HOME/.local/bin/uv"; fi
GOAL052_LAUNCH_STAMP="$stamp" GOAL052_WRAPPER_PID="$$" "$uv_bin" run --locked python - <<'PY'
from pathlib import Path
from datetime import datetime, timedelta, timezone
import json, os
from dsdm_phase1 import goal052_seawfb_dsdm as r
root=Path.cwd(); config=r.config_at(root); base=r.private_root(root,config)
review=r.read_json(root/'evidence/seawfb_dsdm/goal052/twentyfour-worker-review.json')
canary_path=root/config['execution']['canary_receipt']; canary=r.read_json(canary_path)
assert review['status']=='twentyfour_worker_qualification_verified'
assert r.sha256_file(canary_path)==review['canary_sha256']
assert canary['qualified_workers']==24
assert r.sha256_file(root/canary['qualification_driver'])==review['driver_sha256']==canary['qualification_driver_sha256']
assert canary['identity']==review['identity']==r.identity_at(root)
assert canary['runtime']==r.host_runtime('cpu')
assert r.sha256_file(root/'metadata/goal052_full_epoch_profile.json')==review['profile_sha256']
prior=r.read_json(base/'pilot8-launch.json')
assert (base/prior['pilot_exit']).read_text().strip()=='124'
started=datetime.now(timezone.utc)
launch={'started_utc':started.isoformat(),'nominal_deadline_utc':(started+timedelta(days=7)).isoformat(),
'workers':24,'device':'cpu','cap_hours':168,'worker_hour_cap':4032,'termination_allowance_seconds':60,
'session':'dsdm-goal052-continue24','wrapper_pid':int(os.environ['GOAL052_WRAPPER_PID']),
'exit_path':'logs/continue24-'+os.environ['GOAL052_LAUNCH_STAMP']+'.exit',
'wrapper_sha256':r.sha256_file(root/'scripts/goal052_continue24.sh'),
'canary_sha256':r.sha256_file(canary_path),'profile_sha256':review['profile_sha256'],
'qualification_review_sha256':r.sha256_file(root/'evidence/seawfb_dsdm/goal052/twentyfour-worker-review.json'),
'identity':canary['identity'],'review_cadence':'daily at 17:20 Australia/Hobart',
'authorization':'Barry standing compute authority; 15 September concurrency review. Scientific design unchanged.'}
with (base/'continuation24-launch.json').open('x') as stream:json.dump(launch,stream,indent=2);stream.write('\n')
PY
set +e
timeout --signal=TERM --kill-after=60s 168h env GOAL052_WORKERS=24 GOAL052_DEVICE=cpu bash scripts/goal052_launch.sh "$repo_root"
run_status=$?
set -e
printf '%s\n' "$run_status" > "$run_dir/logs/continue24-$stamp.exit.tmp"
mv "$run_dir/logs/continue24-$stamp.exit.tmp" "$run_dir/logs/continue24-$stamp.exit"
exit "$run_status"
