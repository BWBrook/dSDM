# Goal028 Modelling Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and validate a deterministic, leakage-safe target-only modelling foundation and bounded two-species engineering preflight without accessing or scoring the real outer assessment.

**Architecture:** Five focused modules separate immutable contracts, subset construction, model adapters, inner-CV mechanics, and orchestration/publication. One private ingestion factory partitions the combined upstream response and returns only an outer-training `SplitBroker`, an outer-training-key-restricted `FeatureProvider`, and a sealed `OuterVault`. Private Parquet/JSON/model artefacts and privacy-safe tracked aggregate evidence are staged together, semantically replayed, and published atomically.

**Tech Stack:** `uv`-managed CPython 3.12; NumPy; SciPy; scikit-learn; pyGAM; native PyTorch; PyArrow; pytest; standard-library JSON, dataclasses, hashing, resource/platform, multiprocessing, pathlib, and atomic filesystem operations.

## Global Constraints

- Read and obey [`Goal.md`](../../goals/028-modeling-foundation-preflight/Goal.md), [`Decision.md`](../../goals/028-modeling-foundation-preflight/Decision.md), and the accepted [`Tasmanian modelling protocol`](../../plan/tasmanian_modelling_protocol.md).
- Goal021/024/025/026/027 inputs are immutable, exact-digest-bound authorities. Do not modify their source, configuration, evidence, or private products.
- The atomic unit is a unique species-cell row with weight 1. Unknown zero provenance, duplicate keys, balancing, resampling, class weights, imputation, and response-driven feature selection are prohibited.
- Every data-dependent operation is fitted on the relevant inner-training rows only. Neural stopping uses fold `(v+1) mod 5` within CV-training, followed by same-seed complete-CV-training replay for exactly `best_epoch`; assessment fold `v` never enters `fit`. The real outer assessment cannot be opened in any Goal028 mode.
- Use master seed `dsdm-goal028-v1`; real preflight uses `seed00`, plus `seed01` only for paired-neural replay. Five-seed production work is out of scope.
- All estimators use one thread. Canonical compute is Mac mini CPU; between-task process parallelism is bounded by configuration. MPS is optional diagnostic-only. No remote compute.
- Tracked evidence is aggregate only: no grid IDs, coordinates, row payloads, private paths, response identifiers, site/camera identifiers, or private observation timing.
- Stop before real outer prediction/scoring; `q` surfaces; pooled/transfer/multi-head models; final architecture selection; sensitivities; maps; headline comparison; or ecological claims.
- The executor may edit/install/test/generate only the files listed below and may not commit or push. The orchestrator publishes after review.
- Each task ends with one implementer self-review. Independent reviewer gates occur only after Tasks 1–3, Tasks 4–6, and Tasks 7–9, followed by one final whole-diff review after Task 10. Allow at most one focused repair per gate unless a material defect persists.

---

## File map and ownership

**Create**

- `config/modeling_foundation_preflight.json` — exact machine-readable run
  contract, upstream bindings, candidate rows, limits, artefact schemas.
- `src/dsdm_phase1/modeling_contract.py` — config validation, canonical JSON
  and digests, task/seed identities, provenance dataclasses, sealed vault,
  split and feature brokers.
- `src/dsdm_phase1/target_subsets.py` — hierarchical proportional-deficit
  ordering, 25/50/100 prefix endpoints, alias and nesting validation.
- `src/dsdm_phase1/model_adapters.py` — common adapter protocol, fitted-model
  envelope, intercept/scikit-learn/pyGAM/native-PyTorch adapters, registry and
  serialization.
- `src/dsdm_phase1/inner_cv.py` — OOF execution, fold metrics, deterministic
  selection, threshold rule, full-outer-training refit, replay.
- `src/dsdm_phase1/goal028_preflight.py` — synthetic/real modes, provenance,
  atomic private/aggregate publication, full validation and CLI.
- `tests/test_modeling_contract.py`
- `tests/test_target_subsets.py`
- `tests/test_model_adapters.py`
- `tests/test_inner_cv.py`
- `tests/test_goal028_preflight.py`
- `evidence/modeling_foundation_preflight/2026-07-30/*.json` — generated,
  aggregate tracked evidence only.

**Modify**

- `pyproject.toml` — Python 3.12 and approved direct dependencies only.
- `uv.lock` — exact resolved environment.
- `.python-version` — `3.12`.
- `.gitignore` — ignore only
  `data/processed/modeling/goal028-modeling-foundation-preflight/`.
- `src/dsdm_phase1/__init__.py` — export stable Goal028 public contracts only.
- `docs/goals/028-modeling-foundation-preflight/Log.md` — append executor and
  orchestrator receipts; do not rewrite the design checkpoint.

No other files are owned by this plan.

## Canonical configuration contract

`config/modeling_foundation_preflight.json` has exactly these top-level keys:

```json
{
  "identity": {},
  "bindings": {},
  "estimand": {},
  "response": {},
  "partitions": {},
  "subsets": {},
  "features": {},
  "models": {},
  "neural": {},
  "selection": {},
  "threshold": {},
  "replication": {},
  "artifacts": {},
  "compute": {},
  "scope": {}
}
```

Required values:

- `identity`: `schema_version="1.0"`,
  `goal_id="goal028-modeling-foundation-preflight-2026-07-30"`,
  `protocol_version="0.1"`, `master_seed="dsdm-goal028-v1"`,
  `created_at="2026-07-30"`.
- `bindings`: records `{role,path,sha256}` for Goal021 plan/manifest/outputs
  and response; Goal024 plan/manifest/review/outputs/support and private map,
  response-cells, response; Goal025 plan/manifest/review/outputs and private
  assignments/partitioned response/support; Goal026 plan/manifest/review,
  feature contract/fit parameters/private support receipt; Goal027
  Goal/Decision/protocol; `pyproject.toml`; and `uv.lock`. The validator
  compares path safety and bytes. Tracked evidence later emits role and digest
  only, never a private path.
- `estimand`: exact Goal027 conditional relative-suitability wording and
  `goal028_estimates_estimand=false`.
- `response`: key fields `species_id,grid_cell_id`; binary field `pa`; source
  fields `pa_type,response_origin,source_combination`; allowed zero sources
  `survey_supported_absence,pseudoabsence`; `row_weight=1`;
  `class_weight=null`; `resampling=false`.
- `partitions`: `outer_role_field`, `cv_fold_field`,
  `outer_train_value="outer_train"`, folds `fold00`–`fold04`, transforms
  `cv_fold00`–`cv_fold04`, and `outer_vault="sealed"`.
- `subsets`: fractions with formulas `(N+2)//4`, `(N+1)//2`, `N`; ladders
  `ladder00`–`ladder02`; deficit algorithm fields and `full_alias=true`.
- `features`: the Goal026 25 continuous and three categorical names in frozen
  order, `continuous_source="goal026_split_transform"`,
  `categorical_fit_scope="cv_training_rows"`,
  `unknown_category="all_zero_with_count"`, `finite_required=true`.
- `models`: the exact candidate rows from Goal.md and the explicit real
  preflight IDs. Reject extra, missing, duplicate, or reordered IDs.
- `neural`: backend `torch`, device `cpu`, deterministic algorithms enabled,
  one thread, `BCEWithLogitsLoss` with no weights, stopping-fold rule
  `(assessment_fold+1) mod 5`, same-seed reinitialisation, exact-epoch
  complete-training replay, lower-median full-refit epoch rule,
  epoch/patience budgets, status values `patience_stop` and
  `max_epochs_reached`, and replay tolerances `score_atol=1e-6`,
  `parameter_atol=1e-6`.
- `selection`: `mean_fold_roc_auc`,
  `mean_fold_tss_at_oof_threshold`, `canonical_candidate_id`; one threshold
  is derived per candidate from concatenated common-seed-averaged OOF and
  applied unchanged in each equally weighted fold.
- `threshold`: seed-averaged OOF, finite boundaries/midpoints,
  `positive_when="score>=threshold"`, maximise TSS/BA, sorted lower-median
  maximiser `M[(len(M)-1)//2]`, and selected-threshold maximum-TSS replay.
- `replication`: labels `seed00`–`seed04`; real preflight labels; exact
  canonical tuple order; big-endian first-four-byte SHA-256 derivation.
- `artifacts`: exact private and aggregate destinations, schemas, manifest
  names, staging/rollback rules, and forbidden tracked fields/tokens.
- `compute`: Mac mini CPU, estimator threads 1, process workers 2, peak-RSS
  budget 12 GiB, per-task wall budget 20 minutes, MPS non-gating.
- `scope`: two real species and included-row counts, permitted endpoints,
  explicit non-goals, `real_outer_attempted_open_limit=0`, and
  `real_outer_open_limit=0`.

Each private task provenance row must include:

```text
schema_version, run_id, task_id, task_digest, config_digest, git_commit,
species_id, transform_id, cv_fold, fraction_id, ladder_id, subset_digest,
model_family, candidate_id, seed_label, seed_uint32, pair_id, synthetic,
n_train, n_validation, train_positive, train_zero_survey,
train_zero_pseudoabsence, validation_positive, validation_zero_survey,
validation_zero_pseudoabsence, feature_transform_id, transform_digest,
encoder_digest, unseen_level_counts, stopping_fold, best_epoch,
neural_stop_status, outer_attempted_open_count, outer_open_count,
convergence_status, epochs_or_iterations, warnings, runtime_seconds, peak_rss_bytes,
package_versions, python_version, platform, model_path, model_sha256,
oof_path, oof_sha256, publication_state
```

Private `tasks.parquet`, `oof.parquet`, `subsets.parquet`, `run.json`, and
`models/<task_id>.model` may contain identifiers/paths. Tracked
`bindings.json`, `contract.json`, `preflight_summary.json`,
`runtime_summary.json`, `review.json`, and `manifest.json` contain only
aggregate counts, digest roles, ranges/summaries, status, and privacy flags.
Both outer counts are mandatory tracked aggregate fields and semantic-replay
invariants.

### Task 1: Pin the approved Python environment and exact upstream bindings

**Files:**

- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `.python-version`
- Create: `config/modeling_foundation_preflight.json`
- Test: `tests/test_modeling_contract.py`

**Interfaces:**

- Consumes: tracked upstream config/evidence and their frozen digests.
- Produces: a Python 3.12 lock and exact JSON contract consumed by every later
  task.

- [ ] **Step 1: Write the failing environment/config tests**

Add tests that parse `pyproject.toml` and the JSON without importing modelling
packages. Assert Python is `>=3.12,<3.13`; runtime dependencies include NumPy,
SciPy, scikit-learn, pyGAM, PyArrow, and PyTorch; the development dependency
group includes pytest; prohibited packages are absent; all 15 top-level
configuration sections are exact; every bound
path is relative, regular, non-symlinked, and matches its SHA-256; candidate
IDs and preflight IDs exactly match Goal.md; private destinations are ignored;
and both attempted and successful outer-open limits are zero.

- [ ] **Step 2: Run the tests and verify red**

Run:

```sh
uv run pytest -q tests/test_modeling_contract.py -k "environment or raw_config"
```

Expected: fail because the Goal028 config and Python 3.12 dependencies do not
exist.

- [ ] **Step 3: Pin and lock the minimal approved stack**

Run:

```sh
uv python pin 3.12
uv add "numpy>=2,<3" "scipy>=1.15,<2" "scikit-learn>=1.7,<2" \
  "pygam>=0.10,<0.11" "pyarrow>=20,<22" "torch>=2.7,<3"
uv add --dev "pytest>=8,<10"
uv lock
```

Do not add any other modelling or orchestration package. Record exact resolved
versions through the lock digest and runtime provenance rather than duplicating
resolution-dependent versions in prose.

- [ ] **Step 4: Create the exact configuration**

Copy the frozen candidate records and schema above literally. Populate
upstream role/path/digest bindings by reading tracked config/evidence and the
already-frozen private-product digests; do not open private products. After
locking, bind the current `pyproject.toml` and `uv.lock` digests.

- [ ] **Step 5: Run the environment/config tests and lock check**

```sh
uv run pytest -q tests/test_modeling_contract.py -k "environment or raw_config"
uv lock --check
```

Expected: pass; active resolution is Python 3.12 and every binding matches.

- [ ] **Step 6: Implementer self-review for Task 1**

Inspect only the owned diff. Reject policy drift, dependency extras, absolute
paths, unhashed roles, implicit grids, or a nonzero outer limit. Do not commit.

### Task 2: Implement immutable contracts, task identities, seeds, and sealed vault

**Files:**

- Create: `src/dsdm_phase1/modeling_contract.py`
- Modify: `src/dsdm_phase1/__init__.py`
- Test: `tests/test_modeling_contract.py`

**Interfaces:**

- Produces:

```python
class ModelingContractError(ValueError): ...

@dataclass(frozen=True)
class TaskKey:
    species_id: str
    transform_id: str
    fraction_id: str
    ladder_id: str
    model_family: str
    candidate_id: str
    seed_label: str

@dataclass(frozen=True)
class RowKey:
    species_id: str
    grid_cell_id: str

@dataclass(frozen=True)
class RowSet:
    keys: tuple[RowKey, ...]
    pa: np.ndarray
    response_source: tuple[str, ...]
    microcluster: tuple[str, ...]

@dataclass(frozen=True)
class FeatureBatch:
    keys: tuple[RowKey, ...]
    x: np.ndarray
    y: np.ndarray
    unseen_level_counts: Mapping[str, int]
    transform_id: str
    transform_digest: str
    encoder_digest: str

def canonical_json(value: Any) -> str
def sha256_file(path: Path) -> str
def load_run_config(root: Path, path: Path) -> Mapping[str, Any]
def validate_run_config(root: Path, config: Mapping[str, Any]) -> None
def derive_seed(task: TaskKey, purpose: str, master_seed: str = "dsdm-goal028-v1") -> int
def task_id(task: TaskKey) -> str

class OuterVault:
    @classmethod
    def synthetic(cls, rows: Sequence[Mapping[str, Any]]) -> "OuterVault"
    def open(self, authorization: Mapping[str, Any] | None = None) -> RowSet
    @property
    def open_count(self) -> int
    @property
    def attempted_open_count(self) -> int

class SplitBroker:
    def __init__(self, outer_training: RowSet,
                 fold_by_key: Mapping[RowKey, str]): ...
    def inner(self, species_id: str, fold_id: str) -> tuple[RowSet, RowSet]
    def outer_training(self, species_id: str) -> RowSet

class FeatureProvider:
    def __init__(self, substrate: LazyFeatureSubstrate,
                 allowed_keys: frozenset[RowKey]): ...
    def fit_encoder(self, train: RowSet, family: str, transform_id: str) -> Mapping[str, Any]
    def materialize(self, rows: RowSet, transform_id: str, encoder_state: Mapping[str, Any]) -> FeatureBatch

def ingest_private_foundation(
    root: Path, config: Mapping[str, Any]
) -> tuple[SplitBroker, FeatureProvider, OuterVault]
```

`ingest_private_foundation` is the only real ingestion path. It loads and
partitions the combined response internally, constructs `SplitBroker` from
outer-training rows only, allow-lists those keys in `FeatureProvider`, seals
outer rows in a private `OuterVault`, and returns exactly those three objects.
The broker rejects any row whose role is not `outer_train` and has no combined
response argument. A real `OuterVault.open()` increments
`attempted_open_count`, returns no row, and raises
`ModelingContractError("real_outer_vault_sealed")`; `open_count` remains zero.
No config content can unlock it. The synthetic vault opens only when
`authorization={"synthetic": true}`.

- [ ] **Step 1: Add failing tests**

Test canonical JSON/digests; exact seed vector values computed independently
with `hashlib`; task-ID stability; duplicate species-cell, nonbinary response,
unknown zero source, weight drift, and partition mismatch rejection; factory
return shape; broker rejection of combined or outer rows; provider rejection
of non-allow-listed keys; real-vault denial before return; attempted count 1
and successful count 0 after that deliberate synthetic test attempt;
synthetic-only open; inner split class checks; and encoder leakage by
perturbing assessment categories and confirming unchanged training state plus
all-zero assessment encoding/audit count.

- [ ] **Step 2: Verify red**

```sh
uv run pytest -q tests/test_modeling_contract.py
```

Expected: import failure for `dsdm_phase1.modeling_contract`.

- [ ] **Step 3: Implement the minimal contracts**

Validate all row keys before NumPy conversion. Copy arrays, set them
read-only, and sort keys canonically. The private factory partitions before
constructing public objects. `SplitBroker.inner` maps `foldNN` to Goal026
`cv_foldNN`; it never accepts combined rows or `outer` as a fold argument.
`FeatureProvider` rejects keys outside its outer-training allow-list. Encoder
state contains ordered inner-training levels and a canonical digest only.

- [ ] **Step 4: Verify green**

```sh
uv run pytest -q tests/test_modeling_contract.py
```

Expected: pass.

- [ ] **Step 5: Implementer self-review for Task 2**

Trace one validation row through broker/provider and prove it cannot influence
transform or encoder state. Search the module for any real-vault bypass. Do
not commit.

### Task 3: Implement deterministic nested target subsets

**Files:**

- Create: `src/dsdm_phase1/target_subsets.py`
- Test: `tests/test_target_subsets.py`

**Interfaces:**

- Consumes: `RowSet`, canonical JSON and master seed.
- Produces:

```python
@dataclass(frozen=True)
class SubsetEndpoint:
    fraction_id: str
    ladder_id: str
    keys: tuple[RowKey, ...]
    subset_digest: str
    full_alias_id: str | None

def endpoint_sizes(n: int) -> Mapping[str, int]
def hierarchical_order(rows: RowSet, ladder_id: str, master_seed: str) -> tuple[RowKey, ...]
def build_ladders(rows: RowSet, master_seed: str = "dsdm-goal028-v1") -> Mapping[tuple[str, str], SubsetEndpoint]
def validate_ladders(rows: RowSet, endpoints: Mapping[tuple[str, str], SubsetEndpoint]) -> None
```

- [ ] **Step 1: Write failing invariant tests**

Cover `N=1..17` round-half-up sizes, three independent ladders, 25⊂50⊂100,
exact union, response-source then microcluster proportional-deficit choices,
input-order invariance, held-validation perturbation invariance, split-specific
membership, SHA-256 tie determinism, exact full aliases, execute-once identity,
duplicate keys, missing source/microcluster, and single-class failure.

- [ ] **Step 2: Verify red**

```sh
uv run pytest -q tests/test_target_subsets.py
```

Expected: import failure.

- [ ] **Step 3: Implement the ordering literally**

At prefix position `k` (one-based), compute source deficit
`k*n_source/N-selected_source`. Within the chosen source at its one-based
position `k_source`, compute microcluster deficit
`k_source*n_source_cluster/n_source-selected_source_cluster`. Resolve equal
float deficits by full rational cross-multiplication, then SHA-256 priority;
never depend on dictionary/set iteration. Rows inside a bucket are sorted by
their SHA-256 row priority.

- [ ] **Step 4: Verify green**

```sh
uv run pytest -q tests/test_target_subsets.py
```

Expected: pass.

- [ ] **Step 5: Implementer self-review for Task 3**

Use a hand-calculated asymmetric fixture to compare every prefix position,
then stop. Do not commit.

- [ ] **Step 6: Independent reviewer gate for Tasks 1–3**

Review the locked environment/config, structural ingestion seal, task/seed
contracts, and subset invariants as one coherent package. Permit at most one
focused repair unless a material defect persists; rerun only affected focused
checks plus Tasks 1–3 checks. Do not commit.

### Task 4: Implement the common model adapter protocol and conventional adapters

**Files:**

- Create: `src/dsdm_phase1/model_adapters.py`
- Test: `tests/test_model_adapters.py`

**Interfaces:**

- Consumes: `FeatureBatch`, candidate rows, derived seed.
- Produces:

```python
@dataclass(frozen=True)
class FitReport:
    converged: bool
    iterations: int
    best_epoch: int | None
    stopping_fold: str | None
    neural_stop_status: str | None
    warnings: tuple[str, ...]
    runtime_seconds: float
    peak_rss_bytes: int

class FittedAdapter(Protocol):
    def predict_scores(self, batch: FeatureBatch) -> np.ndarray: ...
    def serialize(self, path: Path) -> Mapping[str, Any]: ...

class ModelAdapter(Protocol):
    family: str
    def fit(self, train: FeatureBatch, stopping: FeatureBatch | None,
            candidate: Mapping[str, Any], seed: int,
            exact_epochs: int | None = None) -> tuple[FittedAdapter, FitReport]: ...

def build_adapter(family: str) -> ModelAdapter
def validate_candidate(family: str, candidate: Mapping[str, Any]) -> None
def load_fitted_model(path: Path, expected_sha256: str) -> FittedAdapter
```

Families are `intercept`, `elastic_net`, `gam`, `random_forest`,
`hist_gradient_boosting`, `shallow_ann`, and `residual_mlp`.

- [ ] **Step 1: Add failing conventional-adapter tests**

On a separable and a null synthetic table, test score shape/range/finite
values, row-order restoration, one-thread estimator settings, no sample/class
weights, exact candidate validation, deterministic repeat, serialization
round-trip, tamper rejection, assessment-batch exclusion from `fit`, and
declared nonconvergence failure. Confirm
intercept predictions equal the clipped training positive fraction.

- [ ] **Step 2: Verify red**

```sh
uv run pytest -q tests/test_model_adapters.py -k "intercept or elastic or gam or forest or gradient"
```

Expected: import/adapter failures.

- [ ] **Step 3: Implement conventional adapters**

Wrap conventional estimator warnings; treat a convergence warning or
iteration-budget hit as `converged=false` and a hard failure. Conventional
adapters require `stopping=None` and `exact_epochs=None`. Store a versioned
JSON envelope plus estimator bytes,
candidate record, feature/encoder digests, and SHA-256. pyGAM failure,
nonfinite coefficients, or nonfinite scores is a hard error. Never silently
change a candidate.

- [ ] **Step 4: Verify green**

```sh
uv run pytest -q tests/test_model_adapters.py -k "intercept or elastic or gam or forest or gradient"
```

Expected: pass.

- [ ] **Step 5: Implementer self-review for Task 4**

Inspect each constructor against its config row and verify no default
parallelism, balancing, or hidden early stopping. Do not commit.

### Task 5: Implement native-PyTorch shallow ANN and residual MLP adapters

**Files:**

- Modify: `src/dsdm_phase1/model_adapters.py`
- Modify: `tests/test_model_adapters.py`

**Interfaces:**

- Uses the Task 4 `ModelAdapter` protocol.
- Adds `ShallowANN` (one hidden layer) and `ResidualMLP` (input projection,
  configured residual blocks with bottleneck, GELU, LayerNorm, dropout, scalar
  logit head). Both use unweighted `BCEWithLogitsLoss`, AdamW, fixed minibatch
  order derived from the task seed, CPU deterministic algorithms, and
  stopping-loss epoch discovery. `fit(train, stopping, ..., exact_epochs=None)`
  discovers `best_epoch`; `fit(train, None, ..., exact_epochs=k)` performs a
  fresh exact-`k`-epoch fit and cannot inspect stopping or assessment labels.

- [ ] **Step 1: Write failing neural tests**

Assert module structure and parameter counts, one-hidden-layer shallowness,
residual block count/width/bottleneck, CPU placement, no TensorFlow/Keras/skorch
imports, common-seed determinism within `1e-6`, changed-seed allowance,
stopping-only epoch discovery, same-seed reinitialisation, exact-epoch replay,
assessment-batch rejection by `fit`, finite scores, paired task IDs, and
serialization round-trip. Assert nonfinite loss/gradient/parameters,
optimiser failure, no valid checkpoint, and replay failure are hard failures.
Assert `patience_stop` and `max_epochs_reached` are distinct statuses and a
finite valid maximum-budget checkpoint returns a warning rather than failure.

- [ ] **Step 2: Verify red**

```sh
uv run pytest -q tests/test_model_adapters.py -k "ann or residual or neural"
```

Expected: neural tests fail.

- [ ] **Step 3: Implement minimal deterministic neural training**

Set Python, NumPy, and Torch seeds from the derived seed; call
`torch.use_deterministic_algorithms(True)` and `torch.set_num_threads(1)`.
Checkpoint the best stopping-loss state only to determine `best_epoch`. The
OOF caller discards the discovery fit, reinitialises with the identical task
seed, and calls exact-epoch mode on the complete permitted CV-training
endpoint. Record stopping fold, best epoch, `patience_stop` or
`max_epochs_reached`, device, runtime, RSS, and warnings. Never pass the
assessment batch to `fit`. Treat only nonfinite loss/gradient/parameters,
optimiser failure, no valid checkpoint, or replay failure as neural hard
failure; maximum-budget status alone is warning-only.

- [ ] **Step 4: Verify green**

```sh
uv run pytest -q tests/test_model_adapters.py -k "ann or residual or neural"
```

Expected: pass on CPU.

- [ ] **Step 5: Implementer self-review for Task 5**

Compare target-only residual and shallow paths to confirm they differ only by
declared architecture, not preprocessing, loss weighting, or seed semantics.
Do not commit.

### Task 6: Implement OOF, selection, threshold, and full-training refit

**Files:**

- Create: `src/dsdm_phase1/inner_cv.py`
- Test: `tests/test_inner_cv.py`

**Interfaces:**

- Consumes brokers, providers, subset endpoints, adapters, candidates.
- Produces:

```python
@dataclass(frozen=True)
class FoldOOF:
    task: TaskKey
    keys: tuple[RowKey, ...]
    y_true: np.ndarray
    score: np.ndarray
    roc_auc: float
    best_epoch: int | None
    stopping_fold: str | None
    tss_at_oof_threshold: float | None

@dataclass(frozen=True)
class CandidateOOF:
    candidate_id: str
    seed_folds: Mapping[str, tuple[FoldOOF, ...]]
    oof_threshold: float
    mean_fold_roc_auc: float
    mean_fold_tss_at_oof_threshold: float

@dataclass(frozen=True)
class ThresholdResult:
    threshold: float
    maximizers: tuple[float, ...]
    tss: float
    balanced_accuracy: float

def run_candidate_oof(tasks: Sequence[TaskKey], folds: Sequence[str],
                      endpoint: SubsetEndpoint, candidate: Mapping[str, Any],
                      broker: SplitBroker, provider: FeatureProvider,
                      adapter: ModelAdapter) -> CandidateOOF
def select_candidate(results: Sequence[CandidateOOF]) -> CandidateOOF
def select_threshold(y_true: np.ndarray, seed_scores: Sequence[np.ndarray]) -> ThresholdResult
def refit_outer_training(task: TaskKey, endpoint: SubsetEndpoint,
                         candidate: Mapping[str, Any],
                         broker: SplitBroker, provider: FeatureProvider,
                         adapter: ModelAdapter,
                         fold_best_epochs: Sequence[int] | None
                         ) -> tuple[FittedAdapter, FitReport]
def replay_predictions(model_path: Path, batch: FeatureBatch, expected: np.ndarray, atol: float) -> None
```

- [ ] **Step 1: Write failing metric/integrity tests**

Test exactly one OOF score per outer-training key; gap, duplicate, extra, fold
overlap, and nonfinite rejection; equal fold weighting despite unequal row
counts; per-candidate threshold from concatenated seed-averaged OOF; that
threshold applied unchanged to every fold; ROC-AUC tie broken by
`mean_fold_tss_at_oof_threshold` then ID; threshold boundaries and adjacent
midpoints; `score >= threshold`; lower-median order statistic for odd and even
maximiser sets; selected-threshold maximum-TSS recheck; seed-score averaging;
class checks; full-endpoint alias execution once; and full-outer-training
refit that never asks the vault for outer rows.

For each neural assessment fold `v`, spy on adapter calls and assert stopping
fold `(v+1) mod 5` is used only for epoch discovery, assessment fold `v` is
never passed to `fit`, the discovery fit is discarded, and the same seed
reinitialises an exact-`best_epoch` fit on the complete permitted CV-training
endpoint. Assert full outer-training refit uses sorted
`E[(len(E)-1)//2]` and no stopping or assessment labels.

- [ ] **Step 2: Verify red**

```sh
uv run pytest -q tests/test_inner_cv.py
```

Expected: import failure.

- [ ] **Step 3: Implement exact mechanics**

Compute fold AUC without row pooling. For each candidate, concatenate its
common-seed-averaged OOF scores, derive one threshold, apply it unchanged to
each fold, and equal-weight the five resulting TSS values. Use stable sorted
distinct finite OOF scores; boundary candidates are
`nextafter(min_score,-inf)` and `nextafter(max_score,+inf)`, and internal
candidates are overflow-safe midpoints `a + (b-a)/2`. Classify with
`score >= threshold`. Sort all maximisers, select
`M[(len(M)-1)//2]`, and recompute/assert maximum TSS at that exact value.

For neural OOF fold `v`, use stopping fold `(v+1) mod 5` from the endpoint,
discover `best_epoch` without assessment rows, discard the fitted object,
reinitialise with the same seed, and exact-epoch fit all endpoint rows outside
`v` before assessment prediction. Refit with Goal026 `outer` transform, an
encoder fitted on all outer-training rows, and the lower-median fold-specific
best epoch; pass no validation batch.

- [ ] **Step 4: Verify green**

```sh
uv run pytest -q tests/test_inner_cv.py
```

Expected: pass.

- [ ] **Step 5: Implementer self-review for Task 6**

Hand-check a six-row threshold fixture, an even-sized maximiser fixture, the
unequal-fold selection fixture, and one neural fold's two-fit call trace.
Confirm no assessment batch enters `fit` and no outer value appears in a
signature. Do not commit.

- [ ] **Step 6: Independent reviewer gate for Tasks 4–6**

Review adapters, neural stopping isolation, OOF assembly, candidate tie-break,
threshold order statistic, and exact-epoch refit as one coherent package.
Permit at most one focused repair unless a material defect persists; rerun
only affected focused checks plus Tasks 4–6 checks. Do not commit.

### Task 7: Implement synthetic orchestration, provenance, and atomic publication

**Files:**

- Create: `src/dsdm_phase1/goal028_preflight.py`
- Create: `tests/test_goal028_preflight.py`
- Modify: `.gitignore`

**Interfaces:**

- Produces:

```python
def run_synthetic(root: Path, config_path: Path) -> Mapping[str, Any]
def run_real_preflight(root: Path, config_path: Path) -> Mapping[str, Any]
def validate_publication(root: Path, evidence_dir: Path,
                         private_dir: Path | None, mode: str,
                         full: bool) -> Mapping[str, Any]
def publish_staged_pair(stage_private: Path, stage_evidence: Path,
                        private_dir: Path, evidence_dir: Path) -> None
def main() -> None
```

- [ ] **Step 1: Add failing synthetic end-to-end tests**

Generate an in-memory fixture with both classes, three response sources,
multiple microclusters, unseen validation categories, and a fake outer set.
Run all adapters through five folds, OOF, selection, threshold, serialization,
refit, fake-vault scoring, replay, and publication. Assert exact private and
tracked footprints, aggregate-only tracked JSON, provenance schema, task/pair
digests, full aliases, both attempted and successful real-open counts zero in
private provenance, tracked aggregates, and replay, and deterministic rerun.

- [ ] **Step 2: Add failing tamper/rollback tests**

Mutate config digest, task key, subset row, encoder digest, OOF score, model
byte, aggregate count, manifest byte count, publication state, and fake-vault
flag separately; each must fail semantic replay. Monkeypatch the second rename
to fail and assert neither destination survives.

- [ ] **Step 3: Verify red**

```sh
uv run pytest -q tests/test_goal028_preflight.py -m "synthetic or tamper"
```

Expected: import/orchestrator failures.

- [ ] **Step 4: Implement staging and validation**

Write private tables with explicit PyArrow schemas and stable row order.
Write canonical JSON with newline termination. Build manifest hashes only
after every payload is present. Validate staged bytes and semantics before
rename. Refuse existing destinations and symlinks. On either rename failure,
remove only the just-published Goal028 destination and retain no partial pair.
Tracked privacy walker rejects forbidden keys and absolute/private path text.

- [ ] **Step 5: Run the synthetic gate**

```sh
uv run pytest -q tests/test_goal028_preflight.py -m "synthetic or tamper"
uv run python -m dsdm_phase1.goal028_preflight --root . --mode synthetic
uv run python -m dsdm_phase1.goal028_preflight --root . --validate --synthetic --full
```

Expected: all pass; synthetic manifest says `synthetic=true`.

- [ ] **Step 6: Implementer self-review for Task 7**

Open each tracked JSON and run the privacy walker independently. Inspect both
rollback branches. Do not commit.

### Task 8: Implement the bounded real preflight

**Files:**

- Modify: `src/dsdm_phase1/goal028_preflight.py`
- Modify: `tests/test_goal028_preflight.py`

**Interfaces:**

- `run_real_preflight` accepts no species/candidate override. It reads the
  exact config scope: two species, the 3×3 intercept key path, and all adapters
  at `25%/ladder00` and aliased `100%/full` using
  `null00, enet03, enet07, gam02, rf03, hgb03, ann03, resmlp01, resmlp02`.

- [ ] **Step 1: Write failing bounded-scope tests**

Mock upstream loaders and assert extra species, extra candidate, seed02+,
outer mode, outer transform during inner folds, remote device, process count
above two, or wall/RSS budget overrun fails before fitting. Assert both
species' expected included-row and positive counts are checked and labelled
`included_row_positive_fraction`. Assert the private ingestion factory is the
only combined-response consumer, the returned broker/provider expose only
outer-training keys, and both real outer counts remain zero.

- [ ] **Step 2: Verify red**

```sh
uv run pytest -q tests/test_goal028_preflight.py -k "real_scope or budget"
```

Expected: fail until the real-mode gates exist.

- [ ] **Step 3: Implement fail-closed real loading and scheduling**

Reuse `model_ready_features.validate_evidence(..., full=True)` and its
`load_frozen_inputs` only inside `ingest_private_foundation`; do not alter
Goal026. The factory partitions the combined response internally and returns
only the outer-training broker, allow-listed provider, and sealed real vault.
Build every split-specific ladder from that broker and schedule at most two
independent processes. Terminate staging on the first hard stop. Record poor
AUC as a value, not a failure.

- [ ] **Step 4: Verify mocked real gates**

```sh
uv run pytest -q tests/test_goal028_preflight.py -k "real_scope or budget"
```

Expected: pass.

- [ ] **Step 5: Implementer self-review for Task 8**

Trace exact row memberships, neural stopping/assessment separation, and
transform IDs for one fold/fraction and the full refit. Verify every attempted
and successful real vault count is zero. Do not commit.

### Task 9: Run and validate the bounded real preflight

**Files:**

- Generate: `data/processed/modeling/goal028-modeling-foundation-preflight/2026-07-30/*`
- Generate: `evidence/modeling_foundation_preflight/2026-07-30/*.json`
- Modify: `docs/goals/028-modeling-foundation-preflight/Log.md`

**Interfaces:**

- Consumes: green Tasks 1–8 and exact frozen upstream products.
- Produces: one complete private run and privacy-safe aggregate evidence.

- [ ] **Step 1: Run full synthetic replay immediately before real data**

```sh
uv run python -m dsdm_phase1.goal028_preflight --root . --validate --synthetic --full
```

Expected: passed.

- [ ] **Step 2: Run the real preflight**

```sh
uv run python -m dsdm_phase1.goal028_preflight --root . --mode real-preflight
```

Expected: all required tasks serialize/refit/replay; no real outer row is
returned; no scientific result product is emitted.

- [ ] **Step 3: Run full semantic validation**

```sh
uv run python -m dsdm_phase1.goal028_preflight --root . --validate --real-preflight --full
```

Expected: `status="passed"`, `outer_attempted_open_count=0`,
`outer_open_count=0`, upstream replay passed, privacy passed, and
task/invariant/replay counts exact.

- [ ] **Step 4: Inspect engineering diagnostics**

Reject any missing class, nonfinite value, OOF gap/duplicate, nonnesting,
pairing mismatch, access attempt, conventional convergence failure, neural
hard failure, tolerance failure, or budget overrun. Do not reject merely
because AUC is poor or a finite valid neural checkpoint reports
`max_epochs_reached`. Record `patience_stop` versus `max_epochs_reached`,
runtime/RSS/convergence warnings, both outer counts, and the exact validation
receipt in Log.md without copying private identifiers or scientific metrics.

- [ ] **Step 5: Implementer self-review for Task 9**

Compare private task counts/digests to tracked aggregates and independently
rerun the privacy walker. Do not commit.

- [ ] **Step 6: Independent reviewer gate for Tasks 7–9**

Review synthetic and real orchestration, both zero outer-access counters,
private/tracked provenance, atomic publication, replay, and bounded-resource
execution as one coherent package. Permit at most one focused repair unless a
material defect persists; rerun only affected focused checks plus Tasks 7–9
checks. Do not commit.

### Task 10: Whole-suite verification and orchestrator handoff

**Files:**

- Verify all owned files.
- Modify only if a material defect is found: owned files above.

**Interfaces:**

- Produces an evidence-backed no-commit handoff.

- [ ] **Step 1: Run focused and full checks**

```sh
uv run pytest -q tests/test_modeling_contract.py
uv run pytest -q tests/test_target_subsets.py
uv run pytest -q tests/test_model_adapters.py
uv run pytest -q tests/test_inner_cv.py
uv run pytest -q tests/test_goal028_preflight.py
uv run pytest -q
uv run python -m py_compile \
  src/dsdm_phase1/modeling_contract.py \
  src/dsdm_phase1/target_subsets.py \
  src/dsdm_phase1/model_adapters.py \
  src/dsdm_phase1/inner_cv.py \
  src/dsdm_phase1/goal028_preflight.py
uv lock --check
git diff --check
```

Expected: all pass.

- [ ] **Step 2: Perform one final independent whole-diff review**

Check `git status --short`; verify only owned files changed; search for
prohibited package names, outer-opening paths, balancing/class weights,
private paths in tracked evidence, unresolved placeholder markers, remote
commands, maps, and scientific claims. Compare all public signatures to this
plan.

- [ ] **Step 3: Repair only material defects and rerun affected checks**

If a material defect is found, make at most one focused repair and rerun that
focused test plus the full validation command. Continue only if a material
defect persists; do not begin a general polish loop.

- [ ] **Step 4: Return the acceptance packet**

Report: conclusion; exact changed/generated files; dependency and lock
versions; focused/full test counts; synthetic and real replay status;
outer attempted/open counts; convergence/runtime/RSS; aggregate/private
footprints and privacy check; assumptions and residual limitations; and
whether orchestrator publication is justified. Stop without staging,
committing, or pushing.
