# Plan: Goal 007 Synthetic Normalized Source-Row Gate

## Intent

Extend the Phase 1 synthetic scaffold from mocked request intent to normalized
row readiness. The result should be deterministic summary data over synthetic
rows that proves provenance and `pa_type` semantics survive the gate, without
performing real acquisition, raw-response transformation, spatial work, or
source combination.

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

- `normalize_records` expectations in the Phase 1 plan;
- source provenance requirements;
- true-absence and pseudoabsence separation;
- existing `validate_source_rows`;
- Goal 006 mocked request manifest behavior;
- stop rules before real ALA/camera normalization, grid snapping, and source
  combination.

### 3. Test-First Source-Row Gate

Add tests before implementation. Good test cases are:

- unresolved request decisions block row summaries through the mocked request
  gate;
- unsafe source contracts block row summaries before row summaries return;
- source rows missing required provenance fields fail;
- source rows with invalid `pa_type` fail;
- true-absence rows without `true_absence_rule_id` fail;
- pseudoabsence rows without `pseudoabsence_rule_id` fail;
- valid synthetic rows produce stable summary data;
- valid summaries preserve distinct `presence`, `true_absence`, and
  `pseudoabsence` categories.

The tests should avoid live paths, network calls, and generated output files.

### 4. Implementation Shape

Prefer a small additive function in the existing manifest surface if that keeps
responsibilities clear, for example:

```text
src/dsdm_phase1/manifests.py
```

An alternative small module is acceptable if the executor thinks row summary
responsibility should be separated. Export any public function from
`src/dsdm_phase1/__init__.py`.

The row gate should call existing validators and the Goal 006 mocked request
builder rather than duplicating their logic. It should return plain Python data
that tests can assert directly.

### 5. Fixtures

Use existing fixtures where possible:

- `source_rows.json`
- `source_contracts_resolved.json`
- `source_contracts_unsafe_path.json`
- `decision_manifest_request_resolved.json`
- `decision_manifest_request_ala_unresolved.json`
- `decision_manifest_request_camera_unresolved.json`

Add synthetic fixtures only if mutation inside tests becomes unclear. If added,
keep them tiny and clearly fake.

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

The right result is a conservative row-readiness gate, not a normalizer for real
payloads. It should make later ALA/camera normalization safer by proving that
synthetic rows carry complete provenance and preserve absence categories.
