# Plan: Goal 006 Mocked Acquisition-Request Dry Run

## Intent

Extend the synthetic Phase 1 scaffold from "the acquisition preflight is
coherent" to "the next acquisition request would be auditable and explicitly
not executed." The result should be deterministic request-manifest data, not a
workflow runner and not a real acquisition interface.

## Work Packages

### 1. Live State And Packet Check

- Confirm `pwd`, branch, HEAD, and status.
- Confirm repo-local `AGENTS.md` status.
- Read this goal packet first.
- Record the start checkpoint in `Log.md`.

### 2. Targeted Context Review

Read only the needed planning and scaffold surface:

- `docs/plan/phase1_primary_data_plan.md`
- `docs/plan/phase1_decision_register.md`
- `src/dsdm_phase1/contracts.py`
- `src/dsdm_phase1/manifests.py`
- `src/dsdm_phase1/__init__.py`
- `tests/test_phase1_contracts.py`
- `tests/fixtures/phase1_synthetic/`

Focus on:

- ALA decisions `P1-D003` to `P1-D007`;
- camera decisions `P1-D008` to `P1-D010`, while preserving Goal 004's
  existing `P1-D008` and `P1-D009` source-contract gate;
- the Goal 005 dry-run summary shape;
- synthetic-only fixture policy;
- stop rules before real ALA/camera acquisition.

### 3. Test-First Mocked Request Layer

Add tests before implementation. Good test cases are:

- unresolved synthetic ALA request decisions block request-manifest creation;
- unresolved synthetic camera request/interpretation decisions block
  request-manifest creation;
- unsafe or incomplete source contracts block request-manifest creation;
- valid synthetic decisions, species contracts, source contracts, and Goal 005
  dry-run inputs produce stable mocked request records;
- mocked request creation does not require the synthetic source local paths to
  exist.

The tests should avoid live paths, network calls, and generated output files.

### 4. Implementation Shape

Prefer a small additive function in the existing manifest surface if that keeps
responsibilities clear, for example:

```text
src/dsdm_phase1/manifests.py
```

An alternative small module is acceptable if the executor thinks the request
manifest responsibility should be separated. Export any public function from
`src/dsdm_phase1/__init__.py`.

The mocked request function should call existing validators and the Goal 005
dry-run builder rather than duplicating their logic. It should return plain
Python data that tests can assert directly.

### 5. Fixtures

Use existing fixtures where possible:

- `species_contract_resolved.json`
- `species_contract_unresolved.json`
- `decision_manifest_resolved.json`
- `decision_manifest_source_resolved.json`
- `decision_manifest_source_unresolved.json`
- `source_contracts_resolved.json`
- `source_contracts_unsafe_path.json`

Add synthetic fixtures only if needed for ALA request decisions, camera request
decisions, or expected mocked request output. If added, keep them tiny and
clearly fake. Synthetic "resolved" request values must not be real project
decisions.

### 6. Validation

Run:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tests/test_phase1_contracts.py
git diff --check
git status --short --branch
```

Do not run Phase 0 verification. Do not write runtime outputs.

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

The right result is a conservative mocked request manifest, not a general
acquisition system. It should make the eventual live ALA/camera work safer by
making unresolved decisions and non-execution status explicit in code and tests.
