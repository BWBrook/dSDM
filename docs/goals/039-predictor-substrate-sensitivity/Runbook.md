# Runbook

This runbook records execution boundaries and command slots. The Goal 039
runner and its exact config must bind to the contract in `Decision.md` before
any correlation inspection or fit.

Use the frozen project runtime and one-thread environment selected by the
compute calibration. Replace `<RUNTIME>` and `<MODULE>` only with the recorded
project-local values; do not install packages or alter the raw data.

```sh
RUNTIME=<RUNTIME>
MODULE=<MODULE>
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1 PYTHONPATH=src

"$RUNTIME" -m "$MODULE" plan \
  --config config/dsdm_predictor_substrate_sensitivity.json
"$RUNTIME" -m "$MODULE" mask-audit \
  --config config/dsdm_predictor_substrate_sensitivity.json
"$RUNTIME" -m "$MODULE" canary \
  --config config/dsdm_predictor_substrate_sensitivity.json
"$RUNTIME" -m "$MODULE" run-screen \
  --config config/dsdm_predictor_substrate_sensitivity.json
"$RUNTIME" -m "$MODULE" status \
  --config config/dsdm_predictor_substrate_sensitivity.json
"$RUNTIME" -m "$MODULE" run-confirmation \
  --config config/dsdm_predictor_substrate_sensitivity.json
"$RUNTIME" -m "$MODULE" finalize \
  --config config/dsdm_predictor_substrate_sensitivity.json
"$RUNTIME" -m "$MODULE" validate \
  --config config/dsdm_predictor_substrate_sensitivity.json
```

Run the canary before the screen. Confirmation is forbidden unless at least
one screen lane earns its gate, and only earned lanes may be interpreted at
confirmation. The runner must be resumable, identity-addressed, and
fail closed on corrupt or mismatched leaves. Tracked output is limited to
aggregate metrics, mask/provenance summaries, digests, and validation receipts;
row-level labels, predictions, and private leaves remain untracked.

At every command boundary record source/config hashes, seed scope, mask count,
inventory, and outer-vault attempted/opened counts. The expected outer receipt
is `0/0`. Stop and report if any response-aware input reaches mask construction,
if a mandatory predictor or BIOCLIM block is missing, or if a gate fails.
