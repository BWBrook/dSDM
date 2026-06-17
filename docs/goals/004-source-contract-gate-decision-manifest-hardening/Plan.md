# Plan: Goal 004 Source Contract Gate And Decision Manifest Hardening

## Intent

Turn the existing `source_contracts` stage into an executable dry gate. It
should block until `P1-D007`, `P1-D008`, and `P1-D009` are present and resolved,
and it should validate source-contract metadata without touching real sources.

## Work Packages

### 1. Live State And Packet Check

- Confirm `pwd`, branch, HEAD, and status.
- Confirm repo-local `AGENTS.md` status.
- Read this goal packet first.
- Record the start checkpoint in `Log.md`.

### 2. Targeted Context Review

Read only the needed planning and scaffold surface:

- `docs/plan/phase1_decision_register.md`
- `docs/plan/phase1_primary_data_plan.md`
- `src/dsdm_phase1/contracts.py`
- `tests/test_phase1_contracts.py`
- existing synthetic fixture README and manifests

Focus on:

- `P1-D007`: ALA result versioning
- `P1-D008`: primary camera-trap dataset location
- `P1-D009`: camera true-absence definition
- source manifest fields: source ids, source types, provenance, checksums,
  licenses, sensitivity, and decision ids

### 3. Test-First Extension

Add tests before implementation. Good test cases are:

- `source_contracts` rejects the current synthetic resolved manifest because it
  lacks `P1-D008` and `P1-D009`.
- `source_contracts` rejects a manifest where one of `P1-D007`, `P1-D008`, or
  `P1-D009` is explicitly unresolved.
- `source_contracts` accepts a synthetic-only manifest where those decisions
  are resolved.
- source-contract validation accepts synthetic ALA and camera contracts that
  carry source ids, source types, decision references, versioning/authority
  metadata, checksum metadata, license placeholders, and sensitivity
  placeholders.
- source-contract validation rejects absolute paths, `..` paths, missing
  checksums, or missing provenance fields.

### 4. Fixtures

Extend `tests/fixtures/phase1_synthetic/` rather than creating a second fixture
tree unless there is a compelling reason.

Likely additions:

- `decision_manifest_source_resolved.json`
- `decision_manifest_source_unresolved.json`
- `source_contracts_resolved.json`
- `source_contracts_unsafe_path.json`
- `source_contracts_missing_audit.json`

Every fixture must state that it is synthetic and not a real ALA, camera,
spatial, or predictor source.

### 5. Validator Implementation

Modify the existing scaffold rather than creating a parallel framework.

Likely target:

- update `src/dsdm_phase1/contracts.py`
- export any new validator from `src/dsdm_phase1/__init__.py`
- update `tests/test_phase1_contracts.py`

Keep this standard-library only. Do not add dependencies unless a strong reason
appears and is documented.

### 6. Validation

Run:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
git diff --check
git status --short --branch
```

Optional but useful if source manifests include checksum entries:

```sh
python3 tests/test_phase1_contracts.py
```

Do not run Phase 0 verification.

### 7. Log And Wake-Up

Update `Log.md` with:

- start state;
- files read;
- red/green evidence;
- final validation commands;
- final status;
- wake-up result.

Then send the required wake-up to the `dSDM` orchestrator thread.

## Quality Bar

The right result is a sharper gate, not a larger framework. Prefer a few
obvious validators and crisp tests over abstractions. The source-contract stage
must make it impossible to drift into live ALA or camera ingestion while
authority, versioning, and true-absence interpretation remain undecided.
