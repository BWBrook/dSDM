# Decision

## D030-01 - Goal 025 remains frozen

Retain Goal 025 code, config, products, and evidence unchanged. Its two
full-replay failures observed before this repair are explained by the tracked
CPython 3.14.4 provenance field being replayed under CPython 3.12.13.
Regenerating or rewriting evidence would erase valid historical provenance and
is not an accepted repair. Classify both tests as `real_scope`; execution
requires exact CPython 3.14.4 and explicit
`DSDM_RUN_GOAL025_PRIVATE_REPLAY=1` authorization. Either condition alone is
insufficient.

## D030-02 - Restore the immutable Goal 027 artifact

Restore the protocol path byte-for-byte to the digest frozen by Goal 028's
accepted receipt. Goal 027 remains the prospective scientific design freeze;
Goal 029's decision record and README remain authoritative for the later
five-family implementation closure. No config or accepted evidence is rehashed.

## D030-03 - Preserve the package-wide Goal 029 seal

Keep the accepted `src/dsdm_phase1/*.py` binding. Future Phase 4 code belongs in
sibling `src/dsdm/`, which is outside this seal. Any new or changed Phase 1
module remains fail-closed. Because `pyproject.toml` and `uv.lock` are also
bound, dependency changes require a new versioned execution seal.

## D030-04 - Preserve the conventional seal

The accepted production pair remains bound to its producing checkout and is
not rehashed, regenerated, or claimed as produced by Goal 030. The reconciled
config defines current plan and future authorized synthetic validation only.
Any real calibration, production, recovery, or outer evaluation still requires
separate authorization and the dual-provenance procedure in the Goal 029
runbook. Real outer attempted/open remains `0/0`.
