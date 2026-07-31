# Runbook

Run from the repository root under the locked Python 3.12 environment.

## Engineering and synthetic gates

```sh
uv sync --locked
uv lock --check
uv run pytest -q tests/test_model_adapters.py tests/test_goal029_production.py
uv run pytest -q \
  tests/test_goal028_preflight.py \
  tests/test_inner_cv.py \
  tests/test_model_adapters.py
uv run python -m dsdm_phase1.goal029_production --root . --mode plan
uv run python -m dsdm_phase1.goal029_production --root . --mode synthetic
uv run python -m dsdm_phase1.goal029_production \
  --root . --mode synthetic --validate
```

Synthetic output must use the synthetic vault only. It is disposable and may
be removed after validation. It exercises candidate failure blinding, family
quorum, selected refit, deterministic model replay, paired publication,
source audit, privacy, and partial/unmarked rejection.

Do not resume or delete either retained pyGAM failure stage. The protocol,
registry, gate, and receipt versions intentionally prevent their reuse.

## Real calibration

Run only after separate orchestrator authorization:

```sh
uv run python -m dsdm_phase1.goal029_production \
  --root . --mode calibration
```

The command performs:

1. the four-child zero-fit spawn proof under the one-thread policy;
2. the 56-stratum class-support scan;
3. the frozen two-leaf `hgb04` canary at workers 1 and 2;
4. the 30-leaf representative panel at workers 1, 2, and 4; and
5. the one 337-execution penalised-spline feasibility gate at the selected
   worker count.

The worker-selection and memory/swap rules remain frozen. The GAM gate attempts
five inner fits plus full outer-training refit, serialization, and
response-free challenge replay for every `psgam*` candidate in every stratum.
It repeats
`thylogale_billardierii/fraction100/full/psgam05/seed00` in a separately
spawned one-worker process.

The gate stores only status, bounded diagnostics, and semantic hashes. It must
not retain assessment metrics, thresholds, labels, row identifiers,
prediction values, private paths, or raw exception messages. Every held fold
is predicted through its training-fitted encoder, then checked for length,
finiteness, and `[0,1]` range before only its digest is retained.

All 56 strata require at least two complete candidates including `psgam02` or
`psgam05`. A failed gate retains its sanitized private receipt but publishes
no passing calibration authority. Stop after failure: this is the final
GAM-family attempt, so the next action is global GAM removal rather than a
rerun, wider panel, looser convergence rule, or alternate language.

## Real production

Run only after the penalised-spline gate has published accepted calibration
authority:

```sh
uv run python -m dsdm_phase1.goal029_production \
  --root . --mode production
uv run python -m dsdm_phase1.goal029_production \
  --root . --mode production --validate
```

Production rejects missing, failed, stale, modified, or context-incompatible
calibration evidence. Its 336 GAM candidate statuses must match the accepted
gate exactly. A gate-invalid candidate is a blinded invalid overlay with no
OOF checkpoint or selection eligibility. A gate-complete candidate becoming
invalid is a hard stop.

The `psgam*` payloads are accepted only by Goal029's exact scoped authority.
A generic or Goal028 load must reject them, and all `gamr*` IDs are retired.

Late-stage restart may regenerate only the explicitly permitted source-audit
and transaction metadata. It must preserve checkpoints, selections, models,
memberships, encoders, and failure receipts. Any symlink, unknown inventory
entry, provenance drift, or existing final destination remains a hard stop.

Never open, predict, score, summarize, or inspect the real outer vault during
calibration or conventional production. Publication remains forbidden until
staged artifact validation, the fresh 362-leaf source audit, paired
transaction validation, and the final marker all pass.

## Final engineering gate

```sh
uv run pytest -q
uv run python -m py_compile \
  src/dsdm_phase1/inner_cv.py \
  src/dsdm_phase1/model_adapters.py \
  src/dsdm_phase1/goal029_production.py
uv lock --check
git diff --check
git status --short --branch
```

The completion report must separate engineering validity from scientific
performance and state real outer attempted/open counts exactly.
