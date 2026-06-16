# Plan: Goal 003 Phase 1 Contract Scaffold And Synthetic Fixtures

## Intent

Turn the Phase 1 plan into the smallest useful executable contract. The point
is to create guardrails before real data arrives: unresolved scientific
decisions should stop execution, while purely synthetic resolved decisions
should allow fixture validation to pass.

## Work Packages

### 1. Live State And Layout Check

- Confirm `pwd`, branch, HEAD, and status.
- Confirm repo-local `AGENTS.md` status.
- Inspect root-level files and manifests only enough to choose scaffold layout.
- Record the start checkpoint in `Log.md`.

### 2. Planning Surface Review

Read:

- `docs/plan/phase1_primary_data_plan.md`
- `docs/plan/phase1_decision_register.md`
- `docs/strategic_plan_30000ft.md`
- `README.md`

Extract:

- required contracts
- decision ids that must block real stages
- synthetic fixture requirements
- expected validation behavior

### 3. Scaffold Design

Choose a minimal layout. A good default is likely:

```text
pyproject.toml
src/dsdm_phase1/
tests/
tests/fixtures/phase1_synthetic/
```

But follow existing repo conventions if they point to a smaller or cleaner
choice. Do not migrate the broader repo structure.

### 4. Fixtures

Create tiny synthetic fixtures that are obviously fake and safe to track.

Recommended fixture set:

- species contract fixture
- decision manifest fixture with unresolved values
- decision manifest fixture with synthetic resolved values
- ALA-like occurrence fixture
- camera-trap fixture with true absence
- pseudoabsence or background-candidate fixture
- source/input manifest fixture

Use names and coordinates that cannot be mistaken for real sensitive locations.

### 5. Validators

Add lightweight validators for:

- required decision status
- species contract fields
- source row provenance
- `pa_type` allowed values and separation
- manifest checksums or simple file identity checks

Prefer standard-library Python unless a tiny dependency is already justified by
the repo. Avoid heavy geospatial dependencies in this first scaffold.

### 6. Tests Or Command

Add tests or a script that proves:

- unresolved decisions fail for a stage that needs them
- resolved synthetic decisions pass
- missing provenance fails
- `presence`, `true_absence`, and `pseudoabsence` are accepted as distinct
  categories
- fixtures validate without live data

### 7. Documentation And Log

Add concise docs or README snippets only where discoverability needs them.
Update `Log.md` with commands and outcomes.

### 8. Validation

Run the narrowest meaningful command, likely one of:

```sh
python3 -m pytest
python3 -m unittest
python3 <script>
```

Then run:

```sh
git diff --check
git status --short --branch
```

Do not run Phase 0 verification.

## Quality Bar

The right result is small and opinionated. I would rather accept a modest
validator with crisp tests than a large half-framework. The scaffold should be
boring to run, easy to review, and hard to misuse with unresolved scientific
decisions.
