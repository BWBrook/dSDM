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

The command runs fresh isolated trials at workers 1, 2, and 4, requires
identical semantic outcomes, and selects the largest trial retaining at least
6 GiB free-memory headroom without swap growth. The 30 representative leaves,
all-56 class-support scan, and targeted `gam02`/`gam03` fragility stress are
frozen. Calibration is runtime evidence, not candidate selection, and cannot
be combined across hosts.

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
