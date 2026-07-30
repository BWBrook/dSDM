# Runbook

Run from the repository root under the locked Python 3.12 environment.

## Static and synthetic gates

```sh
uv sync --locked
uv lock --check
uv run pytest -q tests/test_goal029_production.py
uv run pytest -q tests/test_inner_cv.py tests/test_goal028_preflight.py
uv run python -m dsdm_phase1.goal029_production --root . --mode plan
uv run python -m dsdm_phase1.goal029_production --root . --mode synthetic
uv run python -m dsdm_phase1.goal029_production --root . --mode synthetic --validate
```

Synthetic output must be directed to disposable paths, use a synthetic vault
only, and exercise checkpoint resume/tamper rejection, invalid-candidate
blinding, family quorum, selected refit, challenge replay, pair publication,
and partial/unmarked rejection.

## Real calibration

```sh
uv run python -m dsdm_phase1.goal029_production \
  --root . --mode calibration
```

The command first proves four distinct spawned children at zero fits under the
frozen one-thread policy. It then runs the two frozen valid-`gam01` canary
leaves at workers 1 and 2. Both leaves must complete with identical semantics,
and workers 2 must not exceed `1.25` times the workers-1 wall time.

Only then does it run the frozen 30-leaf representative panel at workers 1,
2, and 4. Semantics must match. From trials with at least 6 GiB free memory
before and after and no swap growth, it selects the smallest worker count
within `1.10` times the fastest safe wall time. Finally, it runs the frozen
32-leaf `gam02`/`gam03` fragility panel once at that count. Total calibration
is 126 leaf executions and at most 735 fits; the 56-stratum class-support scan
runs once. Calibration is runtime evidence, not candidate selection, and
cannot be combined across hosts.

The module sets `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`,
`VECLIB_MAXIMUM_THREADS`, and `NUMEXPR_NUM_THREADS` before numerical imports,
then verifies live `threadpoolctl==3.6.0` and PyTorch intra/inter-op state in
parents and children. Do not substitute shell environment settings. The
runtime package remains transitively locked through scikit-learn so Goal028's
accepted `pyproject.toml`/`uv.lock` provenance remains unchanged.

## Real production

```sh
uv run python -m dsdm_phase1.goal029_production \
  --root . --mode production
uv run python -m dsdm_phase1.goal029_production \
  --root . --mode production --validate
```

Do not run production before calibration approval. Never use heterogeneous
host shards. Never open, predict, score, summarise, or inspect the real outer
vault. Stop on leakage, mixed provenance, unknown warning, null/anchor/quorum
failure, selected refit failure, or any requested numerical relaxation.
Publication is forbidden until complete staged artefact validation and the
fresh source audit both pass. Core manifests precede the pair descriptor; the
final acceptance marker is written last. The production command performs that
ordered lifecycle internally and resumes only exact identity-matching staged
checkpoints. The private and tracked inventories are exact allowlists, and a
publication failure restores retryable stage trees where possible without
deleting the only authoritative copy. There are no user-invocable shortcuts
around either gate.

## Final engineering gate

```sh
uv run pytest -q
uv run python -m py_compile \
  src/dsdm_phase1/inner_cv.py \
  src/dsdm_phase1/goal029_production.py
uv lock --check
git diff --check
git status --short --branch
```

The completion receipt must separate engineering validity from scientific
performance and report outer attempted/open counts exactly.
