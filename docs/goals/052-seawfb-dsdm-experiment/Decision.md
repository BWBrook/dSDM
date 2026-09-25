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


## 15 September 2026 — daily monitoring and next concurrency review

Barry requested checks every 24 hours to avoid spending tokens on slow,
predictable progress, and reaffirmed discretion over resource allocation.
The existing heartbeat now runs daily at 17:20 Australia/Hobart. Its first
review follows today's original 17:10 cap; there is no intervening four-hour
check. Preserve active fits and the original cap. The eight-worker pilot has
provided sufficient evidence to make higher concurrency the preferred next
route, subject to current capacity and fresh qualification. Aim first at 24
single-thread CPU workers on deep-server, preserving all prior receipts and
unchanged fitting numerics. This is a qualification target, not a claim of
measured throughput or a launched allocation. Choose the next production
bound after reviewing shutdown and qualification; avoid repeated short caps
that discard costly in-progress fits. Scientific boundaries remain unchanged.


## 15 September 2026 — 24-worker allocation executed

Under standing compute authority, the capped eight-worker run was closed and
its 26 checkpoints verified. A 30-minute-capped 24-worker canary passed in
144 seconds with exact prior numerical agreement and acceptable memory.
Launched 24 single-thread CPU workers for at most 168 hours (4,032 worker-hours)
plus 60 seconds termination, ending 22 September 17:29:30 AEST. Daily reviews
at 17:40 may stop it earlier. This increases CPU use while reducing losses
from repeated short caps. Full-data scaling remains to be measured. Source,
optimizer, budgets, stopping, comparisons and outer boundaries are unchanged.

## 21 September 2026 — prefer kunanyi for remaining independent fits

Barry identified access to 48 PBS nodes, each 28 CPUs / 128 GB RAM, and asked
why that capacity was not being used. Under his standing compute authority,
prepare kunanyi as the preferred continuation route. At most 25 nodes cover
the 700 remaining-pretraining tasks; up to 48 nodes can usefully run the final
target grid. Choose actual concurrency from unfinished tasks, queue limits,
and qualified memory/runtime evidence. Slot ratios are not throughput claims.

Keep the active deep-server allocation and its original deadline while
qualifying PBS. Use the exact frozen runtime in Apptainer because the native
kunanyi GLIBC is too old for the locked Torch wheel. Require exact canary
agreement and a full-row profile on the actual target runtime, then verified
shutdown and imported checkpoints before dispatching disjoint production
shards. Hardware/container probes passed; numerical qualification is pending.
The daily cadence, frozen numerical design and sealed outcomes remain intact.


## 23 September 2026 — bounded 25-node pretraining allocation

Use Barry's standing compute authority to dispatch the verified remaining
pretraining inventory on 25 independent kunanyi nodes, 28 single-thread workers
per node, 110 GiB and 48 hours per PBS job. This covers the native 700-task
inventory in one worker wave per shard, reusing 72 cached fits and leaving
24–26 unfinished fits per node. More nodes would leave still more workers idle
at this stage. Queue availability controls actual concurrency.

The n234 pilot is accepted on exact numerical agreement, native fit contracts,
full-row profiling and PBS/per-worker peak-memory evidence. Its missing sampler
series is an explicit limitation, repaired for production. Every production
host must produce its own canary/profile evidence and pass the independently
reviewed deterministic verifier; prior hostnames are never rebound and no
numerical tolerance is relaxed. This mechanical host gate is an engineering
implementation of the accepted checks, not a scientific amendment.

The fresh import, stopped prior scheduler, 272 checkpoint pairs, selection,
manifest and launch are hash-bound. Persistent rank ownership is authoritative.
Jobs 811265–811289 are the sole active allocation. Retain valid checkpoints on
failure/cap and verify shutdown before deciding any replacement. Final targets
remain behind the full 900-pretraining barrier; sealed-data and scoring limits
remain unchanged. Continue the existing daily heartbeat.

## 25 September 2026 — complete pretraining and 48-node target allocation

All 25 pretraining PBS jobs finished with exit 0 and exact rank completions;
all 900 native checkpoint pairs are verified and preserved locally. The 535
new pairs passed atomic-file, finite-state, seed/init/transfer/freeze,
stopping/replay and data-contract checks. All actual hosts passed exact
qualification; the last eleven profiles were independently checked today.

Use the available 48 nodes for the final-target stage: 28 single-thread workers,
110 GiB and a 48-hour PBS limit per job. The frozen native manifest has 41,250
tasks, including 365 reusable selection-screen fits, leaving 40,885 new fits.
Unlike pretraining's one worker wave, each target shard has hundreds of tasks,
so the requested nodes have useful independent work. Queue availability sets
actual concurrency; no throughput or completion-time claim follows from slots.

Preserve the completed production root and stage under
`/u/bwbrook/codex_kunanyi/dsdm-goal052/targets-20260925`. Require a successful
PBS staging receipt, exact import hashes and manifest replay before dispatch.
Every allocated host must independently qualify before fitting. The external
launch validator now accepts the final-target stage and checks the immutable
900-checkpoint certificate; engineering commit e70fd46 changes no fitting
source, data, configuration, lock or numerical policy. Twenty focused tests
and independent launch review passed.

Keep fixed disjoint ownership and each actual PBS start's original deadline.
No aggregation until all 42,345 unique target leaves validate. The frozen
scientific boundaries and daily 17:40 cadence remain unchanged.


## 25 September 2026 — wait for PBS email and Barry's resumption

Barry superseded daily monitoring with the PBS email workflow used by X-ray
Cavities. Delete the Codex heartbeat and attach one lightweight notification
job to the whole active allocation using `afterany`, so successful, failed and
capped predecessors all release it after they have ended. Use the established
PBS recipient `barry.brook@utas.edu.au`; avoid 48 separate routine end emails.

Job 811800 is verified held on jobs 811750–811797 with end/abort mail enabled.
Wait for Barry to report the email and resume the task. Do not recreate an
automatic polling loop that requires a live TPAC portal session. This changes
notification and handoff only; compute authority, existing caps, scientific
review and sealed-data boundaries remain intact. Allocation termination must
still be distinguished from validated scientific completion.

## 25 September 2026 — validate completed targets beside the data

All 48 target jobs finished successfully and their actual-host qualification,
ownership and rank receipts passed independent review. Run the unchanged
post-fit acceptance on Kunanyi with one CPU / 16 GiB / a four-hour bound while
returning the 5.83 GB leaf archives. Check the full 42,345-leaf inventory and
every saved-fit contract before native aggregation. No new fitting is needed.

The first wrapper failed at import because of a path-depth assumption; preserve
its evidence and use the tested, separately bound replacement 812148. The
frozen numerical source and all scientific gates remain unchanged. PBS sends
end/abort mail for this validation job; wait for Barry's resumption and keep
the daily monitor deleted.
