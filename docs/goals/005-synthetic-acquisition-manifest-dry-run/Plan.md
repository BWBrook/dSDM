# Plan: Goal 005 Synthetic Acquisition-Manifest Dry Run

## Intent

Connect the existing synthetic decision/species/source-contract gates into one
small acquisition preflight. The result should be deterministic manifest
summary data proving a run is ready for later mocked acquisition, without
creating real outputs or touching live sources.

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
- `src/dsdm_phase1/__init__.py`
- `tests/test_phase1_contracts.py`
- `tests/fixtures/phase1_synthetic/`

Focus on:

- run, decision, input, output, QA, and comparison manifest expectations;
- synthetic-only fixture policy;
- existing decision/source/species validators;
- stop rules before real ALA/camera acquisition.

### 3. Test-First Dry Run

Add tests before implementation. Good test cases are:

- unresolved source decisions block the dry-run summary;
- unsafe or incomplete source contracts block the dry-run summary;
- unresolved species contracts block the dry-run summary if the dry run accepts
  a species contract input;
- valid synthetic species, decision, and source contracts produce a stable
  summary with expected run id, stage, source ids, source types, decision ids,
  checksums, license placeholders, sensitivity placeholders, and status.

The tests should avoid live paths, network calls, and generated output files.

### 4. Implementation Shape

Prefer a small additive module if that keeps responsibilities clear, for
example:

```text
src/dsdm_phase1/manifests.py
```

Alternatively, extend `contracts.py` only if the implementation remains small
and obvious. Export any public function from `src/dsdm_phase1/__init__.py`.

The dry-run function should call existing validators rather than duplicating
their logic. It should return plain Python data that tests can assert directly.

### 5. Fixtures

Use existing fixtures where possible:

- `species_contract_resolved.json`
- `species_contract_unresolved.json`
- `decision_manifest_source_resolved.json`
- `decision_manifest_source_unresolved.json`
- `source_contracts_resolved.json`
- `source_contracts_unsafe_path.json`
- `source_contracts_missing_audit.json`

Add a tracked expected manifest fixture only if it makes deterministic output
review easier. If added, keep it synthetic, tiny, and clearly labelled.

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

The right result is a modest preflight summary, not a workflow engine. It
should make the next acquisition-oriented goal safer by proving that the
decision/source manifest bundle is coherent before live behavior is even
available.
