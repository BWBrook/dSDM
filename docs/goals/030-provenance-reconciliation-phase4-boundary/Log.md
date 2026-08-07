# Log

## 2026-08-07 - Start and causal diagnosis

- Confirmed clean base `main...origin/main` at `7f30343`.
- Goal 027 mismatch is tracked baseline inconsistency introduced at `4cab971`:
  the living protocol changed from SHA-256 `6609f3ca4f5100c212db83b3f6bffbed49b6685baeac9ff8242f41c94d7875fb`
  to `e575abcd2fec2271a00438534416f373b372fa2b37decc14f8101742109205de`
  when Goal 029 acceptance recorded the five-family closure, while Goal 028 and
  Goal 029 configs retained the older hash.
- Goal 025 tracked code, config, tests, and `summary.json` have not changed since
  `ce75c7f`. Its frozen summary records CPython 3.14.4. Goal 028's accepted log
  establishes byte-identical strict replay under 3.14.4 and a sole
  `geometry.versions.python` difference under 3.12.13. This is historical
  runtime provenance, not scientific, partition, geometry, private-product, or
  nondeterministic drift.
- Mapped the actual Goal 029 `python -m` source closure. Package initialization
  executes `__init__.py`, `contracts.py`, `manifests.py`, and
  `ala_taxon_resolution.py`; the conventional engine then executes
  `goal029_production.py`, `inner_cv.py`, `model_adapters.py`,
  `modeling_contract.py`, and `target_subsets.py`.
- No ignored/private paths were opened and no model or outer operation ran.

## 2026-08-07 - Source-boundary RED checkpoint

- Added focused tracked-only regressions for the exact nine-file declaration,
  future-module exclusion, bound-file sensitivity, and invalid path rejection.
- The two-test red run failed for the intended missing behavior: the config had
  no `runtime_source_paths`, and `source_tree_digest()` rejected the new
  interface with `runtime_source_glob_mismatch`.
- Command: `uv run --locked pytest -q
  tests/test_goal029_production.py::test_goal029_config_declares_explicit_runtime_source_boundary
  tests/test_goal029_production.py::test_goal029_source_digest_uses_explicit_runtime_boundary`.
- Result: `2 failed`; no ignored/private product, model, or outer access.

## 2026-08-07 - Material review correction

- The accepted Goal 028 receipt freezes both the config digest and Goal 027
  protocol digest `6609f3ca...d7875fb`; changing that config would invalidate
  accepted evidence. The explicit-list hypothesis was rejected before any
  production code, config, or evidence edit.
- Restored the protocol byte-for-byte from the accepted pre-`4cab971` artifact;
  its SHA-256 is again `6609f3ca4f5100c212db83b3f6bffbed49b6685baeac9ff8242f41c94d7875fb`.
- Preserved Goal 029's package-wide source glob. A tracked-only characterization
  passed: sibling `src/dsdm/` changes do not alter its digest, whereas additions
  or edits under `src/dsdm_phase1/` do.
- The two Goal 025 private full-replay tests initially skipped before their
  bodies outside the frozen CPython 3.14.4 runtime; under the active runtime the
  focused result was `2 skipped`. Goal 025 source and evidence remain unchanged.

## 2026-08-07 - Final targeted validation

- Goal 028/029 contract, config-tamper, five-family, runtime-freeze, and source
  digest/namespace checks: `10 passed`.
- Goal 029 plan: `status=pass`; 280 family strata, 1,736 candidate strata,
  6,888 leaves, 34,440 OOF units, 42,840 actual inner fits, at most 952 selected
  refits, 345 source-audit leaves, and outer attempted/open `0/0`.
- `uv lock --check` and `git diff --check`: passed. Final status contains only
  the intended protocol, README, tests, and untracked Goal 030 packet. No
  ignored/private path, model fit, production, recovery, or outer operation
  was run.

## 2026-08-07 - Focused real-scope review repair

- Marked the two Goal 025 private full-replay tests `real_scope` and tightened
  collection-time skipping to require both exact CPython 3.14.4 and explicit
  `DSDM_RUN_GOAL025_PRIVATE_REPLAY=1` authorization.
- Documented the manual authorized invocation in `Runbook.md`; the opt-in does
  not override the runtime check.
- Bounded rerun: the same Goal 028/029 selection returned `10 passed`; with the
  opt-in explicitly absent, the two Goal 025 tests returned `2 skipped`; Goal
  029 plan returned `status=pass` with the frozen counts and outer `0/0`; `uv
  lock --check` and `git diff --check` passed.
