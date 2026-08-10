# Plan

1. Bind Goal035 configuration, aggregate, source modules, and the Goal037
   boundary; validate the exact control identity and parameter counts.
2. Run the fixed largest-dropout canary twice on one private sentinel case,
   checking deterministic predictions, transfer/reset, finite values, and
   resource/timing receipt.
3. Run the resumable Stage 1 cross-product: 4 variants x 8 species x 5 folds
   x 3 seeds = 480 new atomic cells, 1,440 logical lifecycles, and 2,880
   physical fits. The control is imported and reused, not refit or counted.
4. Average common-seed predictions before fold metrics; average folds within
   species and weight species equally. Compute AUC/TSS primary and MCC
   supplementary contrasts and descriptive fold/seed diagnostics.
5. Recompute the complete inventory and eligibility gate in read-only
   finalization. Advance at most one variant by the declared tie-break rule;
   otherwise record `stop_no_stage2`.

Stage 2 is already frozen in the Goal038 configuration. It is materialized only
for the single advanced candidate and follows the six-method, seven-endpoint
workload and fresh-seed confirmation gate recorded in `Decision.md`; no design
change or alternate rescue is allowed.

The conditional implementation is isolated in `capacity_diagnostic_stage2.py`
and `dsdm_capacity_diagnostic_stage2.json`. It reuses Goal035 case preparation,
the neural lifecycle, and private leaf validation. Its `run` command is
resumable and atomic; `status`, `finalize`, and `validate` are read-only over
the private cases except for the aggregate receipt.

Completed with `stop_no_confirmation`; see `Decision.md` and `Log.md`.
