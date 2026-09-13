# Goal 052 decision record

## Status

Protocol frozen on 2026-09-05 before Goal 051 ecological scores were exposed.
This is a prospective protocol record, not a model result.

## Scientific contrasts

The primary contrast is multi-head full fine-tuning against matched target-only
random-init learning. Secondary contrasts are against target plus `q_linear`,
the Goal 051 selected conventional learner, and its `q_linear` augmentation.
The contrasts are paired by target, held fold, endpoint, and seed.

## Leakage and stopping

The entire focal block is excluded from every pretraining auxiliary fit and
auxiliary richness construction, including auxiliary learning-curve
construction. Held folds are excluded from training roles. Stopping uses the
next non-held fold; replay uses the remaining non-held folds at the selected
epoch. Architecture selection is an inner development operation and cannot
access NCP, SEH, or NNC.

The four-architecture winner is selected at target 100%/auxiliary `full`,
seed00. Within each target, rank equal-fold mean ROC AUC descending, pooled OOF
TSS descending, then architecture ID ascending. Across targets, rank mean
target rank ascending, mean target ROC AUC descending, then architecture ID
ascending. All candidates use the same pre-normalized two-layer residual block
with an input projection and identity skips. Leave-one-block-out stability is
diagnostic only. Frozen-versus-target and full-versus-frozen are mandatory
mechanistic diagnostics, not members of the four primary scientific contrasts.
The median selected epoch is rounded for any later retained-full refit.

Before scores, Goal 051 numerical amendments 1, 2 and 3 were versioned after
metric-free q fitting diagnostics and require a repeated metric-free canary.
Amendment 3 adds only the authorized tertiary 20,000-iteration q attempt;
these amendments do not alter the dSDM scientific design. Any further pre-score change requires explicit
versioned authorization; after scores, any scientific amendment requires a
versioned protocol and full rerun.

## Interpretation

The output is a relative habitat-suitability index. Any improvement or null
result is an inner spatial-generalisation result until a later, explicitly
authorized outer evaluation exposes the three frozen IBRA holdouts.


## 12 September 2026 — execution preparation authorized

Barry's instruction to proceed as autonomously as feasible follows acceptance
of Goal051 under the documented family-level gate interpretation. Advance this
frozen experiment through implementation and validation. Its scientific config
remains unchanged, including the historical protocol-only status fields;
this dated decision records the transition from freeze to execution preparation.
The Goal051 acceptance receipt and aggregate supply the bound conventional
controls. No new architecture or performance-informed adjustment is authorized.

Resolve routine implementation details from established project contracts;
consult Barry if a material scientific ambiguity cannot be settled from them,
or if production requires a substantial new compute commitment. NCP, SEH and
NNC outcomes remain sealed. No Goal052 fit has run at this transition.


## 12 September 2026 — capped pilot authorized

Barry approved the prepared 24-hour, two-worker deep-server CPU pilot and
requested a four-hour cadence for checks. The resource cap is 48 worker-hours,
with a 60-second termination allowance. This authorizes the bounded production
pilot described in `ComputeRoute.md`; it does not authorize a full campaign,
cloud allocation, driver change or scientific amendment. Retain completed
checkpoints, stop at the cap and review measured lifecycle cost before the next
resource commitment.


## 13 September 2026 — eight-worker qualification authorized

Barry approved the proposed eight-worker metric-free canary, capped
at 30 minutes (four worker-hours) plus a 60-second termination allowance.
This is qualification only. Preserve the previous canary and completed pilot
checkpoints. Review deterministic repetition, state, memory and contention
before proposing a separately capped production run; no production extension
is authorized by this decision.


## 13 September 2026 — continuation and standing compute authority

Barry instructed: "Launch it. You henceforth have full authority to allocate
compute resources as you see fit." Launch the prepared 48-hour, eight-worker
CPU continuation, with four-hour checks. This grants standing authority for
subsequent compute allocations, route choices and bounded continuations;
resource commitments alone no longer require another approval. Record the
measurement, rationale, allocation and stopping/review point for each change.
The current 48-hour cap remains its operational review point. After reviewing
results, choose and execute the next appropriate allocation autonomously.
Scientific protocol changes and sealed outer assessments retain their existing
boundaries; compute authority does not change the frozen scientific design.
