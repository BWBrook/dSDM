# Goal 031 - dSDM synthetic vertical slice

## Objective

Implement, after this design is accepted, one CPU-only and synthetic-only
vertical slice of the central Tasmanian dSDM experiment. The slice must prove
the method ladder, split scope, anti-circularity rules, transfer semantics,
determinism, and aggregate-evidence boundary before real mammal data or GPU
work. It is not an ecological performance exercise or a production runner.

## Scientific target and scope of inference

Goal 027 remains the scientific authority. The eventual target is a
species-specific relative habitat-suitability index over `D_struct`,
conditional on the accepted 2001--2025 response construction and modelling
design. It is not occupancy, abundance, true prevalence, or a calibrated
probability. Goal 031 uses generated data only, so its inference is narrower:
whether the approved computation and leakage boundaries can execute as
specified. It cannot support any claim about Tasmanian mammals, predictive
skill, spatial transfer, or the value of dSDM.

Goal 029's five-family conventional result is authority for later comparisons,
but those models and products are not reopened here. Goal 030 reserves the new
independent package `src/dsdm/` and freezes `src/dsdm_phase1/` as conventional
authority.

## Frozen outcomes

The implementation must provide:

- a focused `src/dsdm/` package using installed PyTorch, NumPy, and
  scikit-learn only;
- a machine-readable configuration for the exact eight ordered targets, 28
  predictors, five folds, seven nested-learning endpoints, six methods, 24
  residual architectures, and deterministic seeds;
- a planner that describes but does not execute the full contract;
- a deterministic 125-cell fixture with 1,000 species-cell records: 800
  resolved responses and 200 masked unknowns;
- leave-target-out auxiliary construction that excludes pseudoabsences,
  masks unknowns, and averages per-species losses so each of seven auxiliary
  species contributes `1/7` without within-species class balancing;
- the six method paths: matched target-only residual MLP, legacy pooled
  single-head transfer, frozen-trunk multi-head transfer, full multi-head
  fine-tuning, target MLP plus `q_linear`, and target MLP plus `q_deep`;
- a three-architecture CPU sentinel in which one canonical architecture runs
  the complete six-method ladder and two boundary architectures run one
  target-only endpoint each; and
- a deterministic aggregate-only receipt plus independent validation.

All neural execution is CPU float32 with one Torch thread, deterministic Torch
algorithms, split-training-fitted `StandardScaler`, full-batch unweighted
target BCE, species-balanced auxiliary BCE, and exactly 12 AdamW epochs at
learning rate `0.001` without scheduling or early stopping. `q_linear` uses
the exact fixed scikit-learn elastic-net logistic settings in `Decision.md`.

## Exact planner arithmetic

The full planner has eight targets and seven endpoints: three 25% ladders,
three matching 50% ladders, and one shared 100% endpoint. This gives 56
target-endpoint strata. At the selected shared architecture, six methods,
five folds, and five common final seeds give 336 method strata, 1,680
method-fold strata, and 8,400 target-learner fits.

Auxiliary reuse adds 200 pooled-single-head artifacts shared by legacy
transfer and `q_deep`, 200 multi-head artifacts shared by frozen and full
transfer, and 40 deterministic `q_linear` artifacts, for 440 auxiliary fits
and 8,840 final-lifecycle fits. Architecture selection is planned separately:
960 one-seed screen fits plus 480 four-candidate shortlist fits, or 1,440.
The combined declarative workload is therefore 10,280 fits; Goal 031 executes
only the 23-fit sentinel defined in `Decision.md`.

## Acceptance

Acceptance requires witnessed RED then GREEN tests for every new production
behaviour; exact planner and sentinel counts; leakage, anti-circularity,
transfer, and tamper checks; two byte-identical synthetic receipts; an
aggregate-evidence privacy scan; successful CLI `plan`, `run`, and `validate`;
a single sentinel run below 60 seconds on this Mac CPU; selected safe upstream
regressions; `uv lock --check`; and `git diff --check`.

Every receipt must report real outer attempted/open counts exactly `0/0` and
contain no row or cell identifiers, labels, prediction values, species-cell
records, private paths, checkpoints, ecological metrics, or performance
claims.

## Non-goals and stop conditions

Do not use real, ignored, or private data; open or invent outer rows; calibrate
or assess models; map; refit conventional models; add dependencies; build GPU,
remote, distributed, or checkpoint-transaction abstractions; or change
`src/dsdm_phase1/`, Goal 029 config/evidence/products, `pyproject.toml`, or
`uv.lock`.

Stop for review if implementation needs a scientific change, cannot preserve
leave-target-out and split-fitted construction, exceeds the bounded CPU scope,
requires a dependency or protected-file edit, or would emit disallowed
evidence. Stop after one focused self-review/repair pass. Do not commit or push
without separate authorization.
