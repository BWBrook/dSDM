# Decision

## Status

Goal 046 is complete and accepted. Independent validation exited `0` with
status `goal046_ready`, covering five full-target mainland endpoints and 125
final fold-seed tasks. Tasmania remained sealed at `0/0`.

## Contract

Goal 046 is a paired correction of Goal 045, not a new model search. It uses the same three architectures, four arms, seeds, fold assignments, feature transforms, and full-target endpoint. The sole scientific change is strict removal of each focal target's contribution to auxiliary `X=3` support before pretraining or q fitting.

## Verification boundary

The focused suite passed all 16 tests, and the input gate, production run, and
independent aggregate replay all passed. The repository-wide suite returned
704 passed, 2 failed, 2 skipped, and 254 subtests. Both failures are in
`tests/test_dsdm_outer_ready.py` and arise from the pre-existing Goal037
`model_adapters` binding digest mismatch recorded at Goals044-045; Goal046 did
not modify that config or module, so this is not a Goal046 regression. The
detached wrapper did not leave a `run.exit` marker; the completion log and
independent replay validator are the completion authority, and the missing
marker is a non-scientific wrapper anomaly. Tasmania access is explicitly
sealed at `0/0`; no transfer result is available from this Goal.

## Corrected result

The strict correction created 25 q surfaces, 5 strict-q conventional caches,
175 pretraining receipts, 75 architecture-selection receipts, 125 final
receipts, and 500 target fits. Sums of fold/head-specific strict donor-support
auxiliary background-row removals were: Dasyurus `20,370`, Notamacropus
`133,273`, Pseudocheirus `207,647`, Trichosurus `317,107`, and Vombatus
`184,002`. These are row-removal sums, not unique-cell counts; cells can recur
across held folds and response-head constructions. Zero auxiliary presence
rows were removed.

`bridge_control` was reselected with mean species-balanced rank `1.4` (deep
`2.2`, wide `2.4`). At the full endpoint, mean-fold AUC and primary contrasts
were:

- Dasyurus: `0.882759`; versus target-only `+0.009739`, best conventional `+0.002468`, strict-q conventional `-0.001361`.
- Notamacropus: `0.953173`; versus target-only `+0.002744`, best conventional `+0.000391`, strict-q conventional `+0.000747`.
- Pseudocheirus: `0.903409`; versus target-only `+0.010681`, best conventional `+0.005142`, strict-q conventional `+0.004653`.
- Trichosurus: `0.822153`; versus target-only `+0.021093`, best conventional `+0.010814`, strict-q conventional `+0.009467`.
- Vombatus: `0.984055`; versus target-only `-0.000531`, best conventional `+0.000936`, strict-q conventional `+0.000687`.

Across species, the mean contrasts were `+0.008745` versus target-only,
`+0.009772` versus q-neural, `+0.003950` versus best conventional, and
`+0.002839` versus strict-q conventional; the corresponding positive-target
counts were 4/5, 5/5, 5/5, and 4/5. Paired seed-target contrasts were positive
in 21/25 and fold-ensemble contrasts in 20/25. These are descriptive paired
task summaries, not inferential replication counts. Threshold metrics are
secondary: mean-fold TSS was higher than the best conventional model for all
five targets, while pooled MCC was lower for Dasyurus and higher for the other
four.

Compared with the original Goal 045 fraction100/full result, corrected dSDM
AUC changed by `-0.003628`, `-0.002269`, `+0.002064`, `+0.005025`, and
`-0.000309` across the five targets; target-only reproduced exactly. This
confirms the pairing and shows that the strict correction changes magnitudes
without overturning the small mainland signal. Goal 045's original
fraction100/full result is therefore superseded; its 25/50 ladder records are
retained as exploratory history, not strict leave-target-out evidence.

The next boundary is a prospectively frozen, one-shot Tasmania transfer
assessment. It is not part of Goal 046 and must not use Tasmania to tune the
mainland result.
