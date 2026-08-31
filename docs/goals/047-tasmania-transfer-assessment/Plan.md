# Plan

1. Validate every tracked Goal 040/041/042/043/044/046, model, and runtime
   authority without opening Tasmania. **Complete.**
2. Recompute and persist the exact epoch, threshold, conventional coverage,
   mainland range, and categorical-vocabulary authorities. **Complete.**
3. Run the bounded mainland-only canary and commit the implementation plus
   freeze authority. **Complete.** Implementation was frozen in `f46659d`;
   the mainland replay validation repair was committed in `37a5ec3`.
4. Rematerialise the full mainland response heads, validate Goal 042 aggregate
   equality, run resumable q/pretraining/neural/conventional refits, and
   validate the exact inventory and digests. **Complete.** A first refit
   attempt failed safely before fitting or Tasmania access because of a
   four-versus-seven-key replay-summary shape bug. The corrected run reproduced
   all 20 canonical Goal 042 mainland summaries exactly, then completed with
   five q surfaces, 25 pretraining fits, and 142 model artifacts.
5. Build and commit the aggregate opening receipt, then pass the opening gate.
   **Complete.** The opening receipt was sealed in commit `20897ec`; validation
   and the independent final audit were GO.
6. Run the one-shot evaluation with an exclusive durable marker before either
   Tasmania input is opened, then validate the aggregate result. **Complete.**
   No rescue, refit, threshold change, or post-opening tuning was performed.

The tracked aggregate evidence is `evidence/tasmania_transfer/goal047/summary.json`.
Private response, predictor, camera, model, and cell-level payloads remain
untracked or ignored and are not part of this documentation.
