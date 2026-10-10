"""Initialize the verified historical import path before the frozen runner starts.

The frozen outer/close entry points import outer_ready before any leaf loader
has initialized the staged source path. This launcher performs that existing
verified initialization without changing fitting source or accepted receipts.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


def main():
    path = Path(__file__).with_name("tasmania_pseudoabsence_neural.py")
    expected = "ffc6941055ba5485e414ec6cee8472b8fe5fd65609c04cf3158bf49d82caf289"
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError("frozen neural runner changed")
    import tasmania_pseudoabsence_neural as runner
    data, config, _ = runner._load_staged(runner.ROOT, runner.DEFAULT_STAGE_ROOT)
    runtime = runner._attest_runtime(data, config)
    if sys.argv[1:] == ["check-startup"]:
        preparation = runner._load_preparation(runner.ROOT, runner.DEFAULT_OUTPUT, runner.DEFAULT_STAGE_ROOT)
        packages = runner._goal037_package_index(runner.ROOT)
        runner._validate_outer_package_bindings(preparation, packages)
        print(json.dumps({"status": "pass", "fits": 0, "outer_packages": len(packages),
                          "runner_sha256": expected, "runtime": runtime}, sort_keys=True))
        return 0
    if not sys.argv[1:] or sys.argv[1] not in ("run-outer", "close"):
        raise RuntimeError("launcher is restricted to check-startup, run-outer and close")
    return runner.main()


if __name__ == "__main__":
    raise SystemExit(main())
