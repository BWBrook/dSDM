# Goal 029 — Sealed conventional-baseline production

## Objective

Produce the complete inner-OOF conventional baseline panel for the eight
Tasmanian mammals under the Goal027 design, refit and seal every selected
species × endpoint × family × seed model on permitted outer-training rows,
and validate the resulting private/tracked pair without opening or scoring
the real outer assessment.

This is the first production modelling goal. It may select conventional
candidates within frozen families, but it does not compare scientific
performance on the outer set and does not make an ecological claim.

## Recovery amendment

The first full candidate pass stopped correctly at the family-viability gate.
All 2,016 then-planned candidate strata received a terminal status, but the
old GAM panel produced only 133/280 complete candidate strata and 147 invalid
ones: 122 strict nonconvergence failures and 25 fit failures. Only 32/56 GAM
family strata met the former anchor-plus-quorum rule. Every non-GAM family
stratum remained viable. No final selection publication or selected-model
refit proceeded, and real outer attempted/open counts remained `0/0`.

That failed stage is retained as diagnostic evidence and is not canonical
production authority. Barry authorised one bounded pyGAM recovery attempt,
not numerical relaxation or an open-ended GAM search.

## Revised exact scope

- eight ordered species and seven canonical target endpoints;
- five frozen inner folds and all 28 predictors;
- six conventional families and 37 Goal029 candidates;
- six revised cubic pyGAM candidates: `n_splines` 4 or 6 crossed with
  `lam` 10, 100, or 1,000, all with `max_iter=500` and `tol=1e-5`;
- `seed00` for deterministic intercept, GAM, and HGB candidates;
- `seed00`–`seed04` for SAGA elastic net, random forest, and shallow ANN;
- 336 family strata, 2,072 candidate strata, 7,224 candidate-seed leaves,
  36,120 OOF-producing fold units, 44,520 actual inner estimator fits after
  counting ANN discovery plus exact replay, and at most 1,008 selected-model
  refits; and
- a deterministic 362-leaf fresh source audit after staged validation.

The original `gam00`–`gam04` definitions remain unchanged for Goal028 replay.
Goal029 alone selects the new `gamr00`–`gamr05` registry through its
content-bound, explicitly scoped authority context. Those IDs are absent from
the shared canonical registry outside Goal029 and therefore cannot be
accepted by Goal028 or generic adapter loading.

The residual MLP is deferred to Goal030. Community surfaces, pooled,
transfer, multi-head, outer-use, mapping, interpretation, sensitivities, and
birds are outside this goal.

## Acceptance

Goal029 is acceptable when:

1. the formal packet and machine-readable configuration agree exactly;
2. the plan, identities, resumable leaf checkpoints, subset membership
   deduplication, failure/quorum policy, warning classification, challenge
   replays, and paired transaction are tested;
3. synthetic end-to-end and Goal028 compatibility gates pass, including
   proof that every reported BLAS/OpenMP and PyTorch pool is capped at one
   thread;
4. authorised real calibration passes the zero-fit four-child spawn audit,
   two-leaf HGB concurrency canary, 30-leaf representative panel, and revised
   GAM feasibility gate;
5. all 56 GAM species × endpoint strata have at least two complete revised
   candidates, including at least one with `lam>=100`;
6. each complete GAM candidate predicts every actual held fold through the
   encoder fitted on that fold's training rows, passes length, finiteness, and
   `[0,1]` checks, and retains only a prediction digest; it also completes the
   full outer-training refit, serialization, and response-free challenge
   replay without exposing assessment labels, metrics, thresholds, row IDs,
   or prediction values;
7. every gate stage contains the exact bounded diagnostic fields and enums;
   known fit/convergence/prediction failures are candidate-local, while
   unknown, protocol, and authority failures stop;
8. the sentinel repeat runs in a fresh separately spawned single-worker
   process, has a distinct private process-instance digest, and has identical
   status/diagnostics plus, when complete, stage/challenge semantic digests;
9. a gate-invalid GAM candidate enters production only as a blinded invalid
   overlay with no OOF checkpoint or selection eligibility, while any
   gate-complete candidate that becomes production-invalid stops the run;
10. the exact real plan completes or fails closed under the predeclared
   candidate policy;
11. staged artefact-only validation recomputes the full plan and selection,
    then a fresh cache-disabled 362-leaf source audit passes before pair
    publication;
12. every successful receipt reports real outer attempted/open counts `0/0`;
13. tracked evidence contains no response identifiers, private paths, outer
    outcomes, OOF scores, AUC, TSS, thresholds, maps, or claims; and
14. the accepted private/tracked pair is transaction-marked and bound to the
    runtime-critical source tree, configuration, lock, runtime, host,
    upstream authorities, and accepted calibration authority.

Any leakage, unknown zero provenance, family viability failure, unknown
diagnostic or warning, gate/production status drift, selected-model
refit/replay failure, mixed provenance, or proposed numerical relaxation
stops the run for orchestrator review.

If this single revised pyGAM gate fails, Goal029 does not widen the grid or
change convergence criteria. The next separately authorised decision is one
bounded Python-only penalized-spline logistic implementation; failure there
removes GAM from the conventional family set. R fallback and repeated GAM
searches are explicitly out of scope.
