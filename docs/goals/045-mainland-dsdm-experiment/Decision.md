# Decision

## Status

Goal 045 is complete and accepted. The detached production run exited `0`, the
independent validator reconstructed every expected checkpoint, and the tracked
aggregate contains no cell identifiers, coordinates, predictions, or response
rows. Tasmania access remained `0/0`.

## Compute route

Alien was unavailable at the live preflight boundary. The bounded Mac CPU
canary completed the complete data and method path quickly enough to select the
existing three-worker, one-thread-per-fit Mac route. This is an engineering
decision only; the canary does not select an architecture or support a model-
performance claim.

## Scientific boundary

The executable contract exactly preserves the design frozen before Goal 044.
Architecture selection is restricted to mainland CV for the primary full-
fine-tuning arm, using seed00 and equal target-species rank. Final evidence uses
all five paired seeds and all four arms. Tasmania remains sealed until a later,
explicit one-shot transfer-evaluation goal.

The focused Goal 045 tests pass. The repository-wide suite reports 687 passed,
2 failed, and 2 skipped; the two failures are the pre-existing Goal 037 binding
drift already recorded at Goal 044 closeout, not a Goal 045 regression.

The first production launch exposed a non-scientific float32 assertion that
was slightly stricter than machine precision. The repaired guard was checked
against every live head-count pattern and did not change any training weight.
Production then recomputed all evidence under the repaired source identity.

## Result

The equal-species mainland screen selected `bridge_control` with mean rank
`1.4`; it ranked first for four of the five targets. The final experiment
completed all 35 target-endpoint strata, 875 fold-seed tasks, and 3,500 target
fits across the four frozen arms.

The primary full-fine-tuning arm showed a modest but consistent mainland-CV
advantage. Across all 35 strata, its mean AUC change was:

- `+0.0094` against the matched target-only neural model (positive in 34/35);
- `+0.0097` against the neural model with `q_linear` (34/35);
- `+0.0035` against the selected Goal 044 conventional model (30/35); and
- `+0.0024` against the Goal 044 `q_linear` conventional control (30/35).

At the full-target endpoint, the primary arm beat the best conventional model
for all five targets, with a mean AUC change of `+0.0038`. Secondary threshold
metrics were directionally consistent: mean pooled TSS exceeded the best
conventional model by `+0.0044` across all strata and `+0.0064` at the
full-target endpoint. Frozen-trunk transfer was weaker than full fine-tuning.

This is credible evidence of a small, repeatable mainland development signal,
not yet evidence of geographic transfer. Architecture selection and every
reported contrast used mainland CV; the camera-supported Tasmania evaluation
remains sealed for a separately authorised one-shot assessment.

## Verification

- Independent reconstruction: 35/35 endpoint tasks and 875/875 fold-seed
  tasks, status `goal045_ready`.
- Focused suite: 7 passed.
- Privacy gate: Tasmania predictor rows used `0`; Tasmania response rows read
  `0`; no tracked row-level locations, responses, or predictions.
- The earlier repository-wide result remains 687 passed, 2 failed, and 2
  skipped, with both failures confined to the pre-existing Goal 037 binding
  drift recorded at Goal 044 closeout.
