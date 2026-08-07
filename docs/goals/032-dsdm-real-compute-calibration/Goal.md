# Goal 032 - dSDM real-data binding and compute calibration

## Objective

Bind the accepted dSDM engine to the eight-species real **outer-training**
substrate, freeze the exact neural training lifecycle, and measure three
bounded target-only canaries on the Mac mini, `deep-server-ts`, and
`alien-wsl`. Produce a defensible compute recommendation and stop before the
1,440-evaluation architecture search.

This is an implementation and engineering-calibration goal. It estimates no
ecological performance. The eventual target remains a species-specific
relative habitat-suitability index within `D_struct`, conditional on the
accepted 2001--2025 response construction. It is not occupancy, abundance,
true prevalence, or inference outside `D_struct`.

## Required outcomes

1. A local adapter calls Goal029's sealed eight-species foundation without
   modifying `src/dsdm_phase1/`, validates all memberships and provenance, and
   emits only de-identified case arrays.
2. The remote trainer is independent of Phase1 and consumes only the bounded
   bundle. Raw products, row/grid/site/camera identifiers, coordinates, and
   outer assessment material never leave the local data boundary.
3. The real neural input is frozen at 77 columns: 25 split-standardised
   continuous predictors plus all 52 response-independent Goal026 categorical
   indicators. Column 78 is reserved for later `q` controls; Goal032 fits no
   `q` surface.
4. Goal028's rotating stopping fold, exact-epoch replay, optimiser, batching,
   weighting, and deterministic seed rules are executable on CPU and CUDA.
5. The exact light, medium, and heavy cases in the config run twice on each of
   the three hosts. Same-host model and prediction digests repeat; cross-host
   equality is not required.
6. Only the leading serial host receives the six-task concurrency panel. The
   final recommendation reports central and worst-case projected duration,
   memory headroom, and the selected worker policy.
7. Auxiliary construction is validated, not fitted: target exclusion,
   pseudoabsence exclusion, unknown masking, seven-species presence, equal
   species contribution, and aggregate counts must all pass.
8. All three canary hosts use isolated Python 3.12 environments with NumPy
   2.2.6 and PyTorch 2.7.1. Mac/deep-server use official CPU wheels; Alien uses
   the official cu118 wheel compatible with driver 546.01. This does not alter
   the repository lock or become Goal033 production authority.

## Acceptance

- Test-first implementation covers contract drift, data leakage, de-identifying
  export, stopping/replay semantics, deterministic repeats, host receipts,
  workload arithmetic, and privacy failures.
- The local binding reports exactly eight species, 11,039 outer-training rows,
  five folds, unique species-cell keys, exact Goal028 subset replay, 77 target
  columns, and outer attempted/open `0/0`.
- The bounded calibration executes exactly 24 logical evaluations and 48
  physical fits: 18 serial logical evaluations/36 fits plus six concurrency
  tasks/12 fits.
- Every host receipt proves the frozen isolated runtime. The current Linux
  lock's Torch/CUDA resolution is not used as evidence of Alien compatibility.
- The future architecture workload is reported as 1,440 logical evaluations
  but 2,880 physical discovery/replay fits.
- All same-host repeats have identical semantic, model, and prediction digests.
  Timing and memory values may differ. Cross-host digests are descriptive only.
- The tracked receipt contains aggregates, digests, runtimes, memory, and the
  recommendation only; it contains no response rows, identifiers,
  predictions, losses, ecological metrics, private paths, or performance
  claims.
- Relevant focused tests, CLI plan/bind/run/validate/recommend paths,
  `uv lock --check`, privacy scans, and `git diff --check` pass.

## Stop boundary

Do not run the architecture screen or shortlist; start a long `tmux` job; open
or copy the real outer assessment; fit a six-path real ladder or `q` surface;
calculate AUC, TSS, MCC, PR AUC, thresholds, or ecological comparisons; change
dependencies, `uv.lock`, or sealed Phase1. Implementation workers must not
commit or push. After all acceptance gates pass and the orchestrator accepts
the goal, the orchestrator may commit and push under Barry's standing
authority. Stop after one focused review/repair pass and return the compute
recommendation to Barry.
