# Decision

## D031-01 - Independent Phase 4 package and immutable authorities

Implement under sibling `src/dsdm/`; do not import production behaviour from
or modify `src/dsdm_phase1/`. Reuse only installed PyTorch, NumPy, and
scikit-learn. The machine-readable configuration will live at
`config/dsdm_synthetic_vertical.json`, and the accepted aggregate receipt at
`evidence/dsdm_synthetic_vertical/goal031/receipt.json`.

The exact ordered targets are:

1. `thylogale_billardierii`;
2. `notamacropus_rufogriseus`;
3. `trichosurus_vulpecula`;
4. `pseudocheirus_peregrinus`;
5. `vombatus_ursinus`;
6. `sarcophilus_harrisii`;
7. `dasyurus_maculatus`; and
8. `dasyurus_viverrinus`.

The folds are `fold00`--`fold04`. The endpoints are
`fraction25/ladder00`--`ladder02`, the matching
`fraction50/ladder00`--`ladder02`, and `fraction100/full`. Each 25% subset is
nested within its same-numbered 50% subset, and all are nested within the one
100% endpoint.

## D031-02 - Balanced synthetic observation process

Generate 125 synthetic cells with 28 shared numeric predictors and eight
species-cell rows per cell. For every species, each fold contains exactly 8
presences, 6 survey-supported absences, 6 pseudoabsences, and 5 unknowns.
Thus every species has 40/30/30 resolved provenance counts plus 25 unknowns;
the complete fixture has 320 presences, 240 survey-supported absences, 240
pseudoabsences, and 200 unknowns.

Holding one fold leaves, per species, 32 presences, 24 survey-supported
absences, 24 pseudoabsences, and 20 unknowns. Each deterministic ladder must
select exact target-training compositions 8/6/6 at 25% (20 rows), 16/12/12
at 50% (40 rows), and 32/24/24 at 100% (80 rows). Target models may use all
three resolved provenance classes. Held-fold scoring is internal and masks
its five unknowns; neither labels nor predictions enter evidence.

For seven auxiliary species, the raw split-training pool is 700 rows. Masking
140 unknowns and excluding 168 pseudoabsences leaves exactly 392 usable rows:
56 per species, comprising 32 presences and 24 survey-supported absences.
The target species is absent from the auxiliary pool. There are no outer rows
in the fixture, and every command and receipt reports real outer
attempted/open `0/0`.

## D031-03 - Executable anti-circularity and species balance

All preprocessing and auxiliary fitting is scoped to the current fold's
training cells. Auxiliary inputs contain only the 28 predictors: no species
identity, target response, provenance encoding, fold label, subset membership,
or cell identifier is a feature. Unknown responses are masked before loss;
pseudoabsence rows are rejected, not assigned zero weight. Auxiliary loss is
the mean of seven within-species mean losses. This preserves within-species
class imbalance while fixing each species contribution at `1/7`.

`q_linear` is a fixed-hyperparameter, split-fitted pooled elastic-net logistic
model with no species identity. `q_deep` is the sigmoid scalar from the same
split-fitted pooled single-head nonlinear network used for legacy transfer.
Each scalar is generated for target rows without target labels and appended as
one covariate to a freshly initialised matched target learner. The scalar is a
control covariate, not an occurrence probability.

## D031-04 - Six paths and valid pretraining reuse

The exact method IDs are:

- `target_only_resmlp`;
- `legacy_pooled_finetune`;
- `multihead_frozen_trunk`;
- `multihead_full_finetune`;
- `target_plus_q_linear`; and
- `target_plus_q_deep`.

For a target/fold/seed, one pooled single-head pretrain is cloned for legacy
fine-tuning and also supplies `q_deep`; one multi-head pretrain is cloned for
both frozen-trunk and full fine-tuning; and one deterministic `q_linear` fit is
reused across downstream seeds. These auxiliary artifacts are reused across
all seven target endpoints because their allowed auxiliary rows do not change.
No trained target state is shared across endpoints or methods. Target-only and
transfer learners have the same trunk and head shapes, optimiser budget, and
seed; q learners differ only by the required 29-input stem.

## D031-05 - Exact 24-candidate residual registry

Every candidate uses a width-preserving residual trunk with GELU and LayerNorm.
The input stem absorbs either 28 or 29 covariates. `constant` repeats the listed
bottleneck in every block; `taper` changes the bottleneck once after the trunk
midpoint to `max(16, bottleneck / 2)`. Dropout and AdamW weight decay are
bounded as shown.

| ID | Blocks | Width | Bottleneck | Shape | Dropout | Weight decay |
|---|---:|---:|---:|---|---:|---:|
| `resmlp00` | 2 | 64 | 16 | constant | 0.00 | 1e-5 |
| `resmlp01` | 2 | 64 | 32 | taper | 0.10 | 1e-4 |
| `resmlp02` | 2 | 64 | 64 | constant | 0.20 | 1e-3 |
| `resmlp03` | 2 | 128 | 16 | taper | 0.20 | 1e-4 |
| `resmlp04` | 2 | 128 | 32 | constant | 0.00 | 1e-3 |
| `resmlp05` | 2 | 128 | 64 | taper | 0.10 | 1e-5 |
| `resmlp06` | 2 | 256 | 16 | constant | 0.10 | 1e-3 |
| `resmlp07` | 2 | 256 | 32 | taper | 0.20 | 1e-5 |
| `resmlp08` | 3 | 64 | 16 | taper | 0.20 | 1e-3 |
| `resmlp09` | 3 | 64 | 32 | constant | 0.00 | 1e-5 |
| `resmlp10` | 3 | 64 | 64 | taper | 0.10 | 1e-4 |
| `resmlp11` | 3 | 128 | 16 | constant | 0.10 | 1e-5 |
| `resmlp12` | 3 | 128 | 32 | taper | 0.20 | 1e-4 |
| `resmlp13` | 3 | 128 | 64 | constant | 0.00 | 1e-3 |
| `resmlp14` | 3 | 256 | 16 | taper | 0.00 | 1e-4 |
| `resmlp15` | 3 | 256 | 64 | constant | 0.20 | 1e-5 |
| `resmlp16` | 4 | 64 | 16 | constant | 0.10 | 1e-4 |
| `resmlp17` | 4 | 64 | 32 | taper | 0.20 | 1e-5 |
| `resmlp18` | 4 | 64 | 64 | constant | 0.00 | 1e-3 |
| `resmlp19` | 4 | 128 | 16 | taper | 0.00 | 1e-5 |
| `resmlp20` | 4 | 128 | 32 | constant | 0.10 | 1e-3 |
| `resmlp21` | 4 | 128 | 64 | taper | 0.20 | 1e-4 |
| `resmlp22` | 4 | 256 | 32 | constant | 0.20 | 1e-4 |
| `resmlp23` | 4 | 256 | 64 | taper | 0.00 | 1e-3 |

The declarative architecture stage screens all 24 candidates on the 100%
endpoint for eight targets, five folds, and one seed (960 fits), then evaluates
exactly four shortlisted candidates for eight targets, five folds, and three
seeds (480 fits). It selects one shared architecture without outer evidence.
Goal 031 does not execute or claim this selection.

## D031-06 - Exact CPU sentinel

The sentinel uses target `sarcophilus_harrisii`, held fold `fold00`, common seed
`31031`, and the ladder00 endpoints with 20, 40, and 80 target-training rows.
`resmlp01` is the canonical sentinel architecture and runs all six methods at
all three endpoints: 18 target fits. Three auxiliary fits are made once and
reused: pooled single-head, multi-head, and `q_linear`. The architecture
sentinel is `resmlp00`, `resmlp01`, and `resmlp23`; because `resmlp01` is
already exercised, `resmlp00` and `resmlp23` add one target-only 25% fit each.
Total execution is exactly 20 target fits, 3 auxiliary fits, and 23 fits.

The sentinel uses deterministic CPU algorithms, one Torch thread, full-batch
updates, fixed epochs, and no checkpoint persistence. It proves execution and
equivalence boundaries only; losses and synthetic prediction quality are not
evidence.

## D031-07 - Evidence and residual scientific risk

The canonical receipt is byte-stable JSON with sorted keys and no timestamps,
durations, machine names, absolute paths, row-level material, model weights,
labels, predictions, ecological metrics, or performance language. It records
only contract/config digests, aggregate fixture counts, planner counts,
aggregate fit/path completion counts, determinism status, runtime budget,
privacy status, and outer attempted/open `0/0`.

This goal can expose leakage, masking, transfer, reuse, planner, and numerical
determinism defects. It cannot diagnose real-data identifiability, detection
bias, mixed-zero validity, spatial or temporal autocorrelation,
non-stationarity, extrapolation, class scarcity, calibration, architecture
selection uncertainty, or ecological generalisation. Those remain explicit
later-phase risks. A Sol Max audit is not justified for this design-only or
synthetic implementation gate; it becomes justified before accepting a
central real-data implementation or consequential ecological claim.

## D031-08 - Synthetic execution contract

Goal 031 neural execution is CPU `float32` with one Torch thread and
`torch.use_deterministic_algorithms(True)`. `StandardScaler` is fitted only on
the permitted split-training predictors. Every neural fit uses full-batch
`BCEWithLogitsLoss`, exactly 12 epochs, AdamW learning rate `0.001`, no
scheduler, no early stopping, and its architecture-specific weight decay.
Target loss is unweighted. Auxiliary loss is the mean of the seven
within-species mean losses.

`q_linear` uses scikit-learn `LogisticRegression` with
`penalty="elasticnet"`, `solver="saga"`, `C=1.0`, `l1_ratio=0.5`,
`max_iter=2000`, `tol=1e-6`, a derived deterministic random state, and one
effective thread. Aggregate provenance and class counts are permitted in the
receipt. Row-level response labels, identifiers, predictions, and
species-cell records remain forbidden.

## D031-09 - Review repair: execution binding and matched randomization

The accepted receipt is bound to the actual validated fixture and completed
sentinel through aggregate fixture and execution SHA-256 digests. Receipt
construction accepts the executed fixture explicitly. Independent validation
regenerates the canonical fixture, executes the 23-fit sentinel again, and
compares its aggregate fixture summary/digest and execution digest. Rehashing a
fabricated count or digest bundle cannot establish authority. Digests disclose
no model state, response row, identifier, or prediction.

Before any fit, `validate_fixture` enforces the exact `(125, 28)` finite
predictor matrix, complete unique species-cell cross-product, cell-to-fold
mapping, per-fold provenance counts, label/provenance mapping, predictor
references, and all 25/50/100 compositions and nesting relations. Receipt
subset sizes come from those executed validated endpoints.

Target initialization and fit seeds are functions only of target, fold, base
seed, endpoint, and architecture; method is excluded. All 28-input target
paths begin from one common initialization. Multi-head transfer replaces only
the common model's shared representation, preserving its common target head;
frozen and full variants therefore begin byte-identically. Legacy transfer
replaces the whole common state as its treatment. Both 29-input q controls
begin byte-identically. Frozen stems, trunks, and final normalization remain
in evaluation mode during head fitting, while the head remains trainable.
