# dSDM: Fresh-Task Handover

Prepared for Barry Brook's successor research collaborator, 2026-09-05.
Repository: `/Users/bwbrook/papers/dSDM`. Original handoff followed `8be8ec6`;
execution status was refreshed on 2026-09-08 for the move from Mac production
to resized Nectar at Barry's request.

## Latest Goal052 state — 18 September, 17:43 AEST

The eight-worker allocation closed at its original 17:10 AEST cap (exit 124),
with 26 verified pretraining checkpoints, including 24 new completions in
48 hours, and zero target leaves. All payload/receipt hashes and fit/data
contracts passed; no workers or semaphore files remained after shutdown.

The new 24-worker CPU qualification passed: 48 jobs, exactly two per PID,
with all non-runtime result fields identical to the previous qualification.
It took 144 seconds, with 2.564 GiB peak worker RSS and 58.643 GiB maximum
sampled group RSS. The prior eight-worker receipt is archived. The active
canary is `metadata/goal052_canary.json`; its separate driver and review are
hash-bound. Fitting source remains `e309ca8` (digest `fce7fb52...`).

The seven-day/24-worker continuation launched at **17:29:30 AEST on
15 September** in deep-server tmux `dsdm-goal052-continue24`, at
`/data/codex/repos/dSDM`. All 24 workers are active, and the first 26 scheduler
completions reuse the unchanged existing checkpoints. The cap is
**22 September, 17:29:30 AEST**, plus 60 seconds termination. Private
`continuation24-launch.json` binds the launch; tracked
`evidence/seawfb_dsdm/goal052/continuation24-launch-review.json` adds actual
PIDs, log path and reuse verification. Runner PID 45460; timeout PID 45451.

Daily checks now run at **17:40 Australia/Hobart**, after the final cap on
its last day. This supersedes 17:20 and four-hour instructions below. Barry
retains standing compute authority: review actual throughput and capacity,
and choose subsequent bounded allocations autonomously. No new scientific
or numerical amendment is authorized. The sealed outer boundaries remain.

Third daily check: **116/200 screen-pretraining checkpoints are verified**,
including 33 new fits since yesterday (90 since this allocation started).
All 232 payload/receipt hashes, stopping/replay and data-contract checks passed;
zero target leaves. All 24 original workers remain active at 99.9% CPU, with
about 81 GiB RAM available and no swap use. New completed lifecycles took
12.13–21.97 hours (mean 16.55), selected/replayed epochs 1–5. Source/runtime/
qualification/launch bindings are unchanged. Continue the same allocation
and daily cadence. See `continue24-day3-review.json`.

## Start Here

The primary cross-AI venue is the Correspondence project `dsdm`, discussion
32, "Fable's arrival review: programme, Goal 052 compute, and pre-score analysis plan".
Barry invited Fable as an external scientific advisor and reviewer; Astra
handles implementation and execution. Consult and reply there when active;
bring Barry unresolved scientific decisions requiring his judgement. Board
discussion does not itself amend frozen protocols or dispatch another model.


Work directly with Barry here. The Chief-of-Staff worktree and named
action-agent `quoll` arrangement are retired for this project. Use native,
bounded subagents when useful; do not reconstruct that management machinery.

This note gives the current orientation; linked protocols, decisions, code,
and evidence supply the detail. Some historical roadmap paragraphs lag behind
the work. The mainland-to-Tasmania transfer assessment is complete; it is
distinct from the still-deferred original Tasmania outer test.

## Scientific Purpose And Findings

We test whether species-aware, multi-head neural pretraining learns a useful
environmental representation that transfers to a focal species excluded from
pretraining. Fine-tuning must beat strong target-only controls, not convenient
weak baselines. Outputs are **relative habitat-suitability indices**, not
occupancy probabilities. A sound negative result is a successful experiment.

The programme has three steps, followed by synthesis and substantial manuscript
revision:

1. **Eight Tasmanian mammals: machinery prove-out.** Rebuilt acquisition,
   cleaning, predictors, responses, spatial partitioning, conventional models,
   and the PyTorch dSDM workflow. High prevalence, restricted geography, and
   only seven auxiliary species made this a difficult transfer-learning test.
   Inner comparisons found no convincing dSDM advantage; larger networks and
   reduced predictors did not rescue it. Preserve this finding. The original
   held-patch outer assessment remains sealed/deferred. Macropus giganteus was
   excluded from the original nine because historical range contraction makes
   current distribution a poor proxy for potential suitability.
2. **Mainland mammals transferred to Tasmania: completed bridge experiment.**
   Used a richer mainland pool, portable predictors, and five shared targets,
   assessed against Tasmania's camera-supported absences. Goal 046
   corrected auxiliary effort-support leakage and supersedes Goal 045's
   full-data/full-auxiliary result. Small corrected mainland-CV gains did not
   transfer: Goal 047's one-shot Tasmania test found mean AUC about 0.556 for
   full dSDM versus 0.584 for selected conventional models. This descriptive
   five-species null stands; no Tasmania-informed architecture or threshold
   rescue. See the [accepted decision](docs/goals/047-tasmania-transfer-assessment/Decision.md).
3. **Southeastern Australian woodland/forest birds (SEAWFB): current stage.**
   Many more auxiliary species and more varied prevalence/environments test
   the scaling hypothesis. Better performance is a hypothesis, not an
   acceptance criterion. Tasmania is ordinary training geography here.

The scalar `q_linear` control tests general community suitability against
learned neural representations: pooled elastic-net environmental predictions,
equal total contribution per auxiliary species, no species-ID predictor.
It is not an observed richness layer.

## Frozen Bird Design

Goals 048-050 established the design and reproducible modelling foundation:

- Contemporary 2001-2025 evidence on 0.01-degree cells. The bird response
  substrate comes from an ALA aggregate species-cell census, not legacy R
  tables or a claimed raw-occurrence-row download.
- 505 effort-donor taxa, 183 eligible modelling heads, 157 focal targets.
  The 73 primary targets have nested 25/50/100% target-data endpoints; the
  remaining 84 have full-data endpoints only. These supersede the initial
  40-species feasibility panel.
- Three complete IBRA regions plus their external 50-km buffers are excluded
  simultaneously: NCP (Naracoorte Coastal Plain), SEH (South Eastern Highlands),
  and NNC (NSW North Coast). Their evaluation outcomes remain sealed.
- Retained training uses five frozen spatial folds of projected 50-km blocks,
  seed 394, and a portable 24-predictor set encoded into 103 features.
- X10 effort-supported backgrounds are primary; X20 is evaluation-only
  sensitivity. Richness measures sampling support, not a predictor or proof
  of true absence. Preserve natural prevalence rather than balancing classes.
- Ten focal-species blocks govern cross-fitting. Remove the **whole focal
  block from both auxiliary response heads and auxiliary donor richness**.
  Target fitting/evaluation instead uses the frozen target-specific support
  rule. Exclude held spatial folds from fitting, including transforms and
  stopping decisions. Do not improvise a simplified exclusion rule.

Primary selection uses mean-fold ROC AUC; training out-of-fold TSS supplies
tie-breaking and threshold selection. BA, MCC, sensitivity, specificity,
prevalence, and fold variation provide complementary interpretation. Outer
outcomes must never choose architectures, features, thresholds, or repairs.

## Goal 051 benchmark — accepted 12 September

The conventional benchmark is implemented and accepted with its documented
candidate-failure limitation; the dated closeout below is authoritative.
Its five families are intercept-only null, elastic-net logistic regression,
random forest, histogram gradient boosting, and a shallow one-hidden-layer ANN.
The statistical families use scikit-learn; the ANN and dSDM use PyTorch.
The grid has 303 base endpoints, 449 q conditions, and 150 shared q surfaces.

A metric-free canary exposed numerical problems in q fitting. Correction
`c14bc47` is already committed and pushed: use `w/k` and `C*k`, where
`k=max(w)`, preserving the penalized objective, and distinguish convergence
warnings from unrelated warnings. Recorded verification: **31 tests passed**.
Protocol v3 allows one 5,000-to-10,000-iteration retry but requires convergence.
Do not rerun obsolete v2 or mistake all its warning-triggered failures for
proven iteration exhaustion.

Corrected canaries were launched on 5 September in detached sessions:

| Host | Checkout | tmux session |
| --- | --- | --- |
| Mac mini | `/Users/bwbrook/papers/dSDM` | `dsdm-goal051-canary-mac` |
| `deep-server-ts` | `/data/codex/repos/dSDM` | `dsdm-goal051-canary` |

The successor's read-only inspection found both canary sessions finished. Mac
exited 0 with all five receipts and a host summary. Deep-server produced two
serial receipts, then exited 1 during mixed concurrency with PyTorch's
autograd/fork threading error; no completed deep-server host summary exists.
Neither host had a production session or run log.

The authorized code sweep removed the abandoned Goal029 P-spline implementation,
merged repeated q standardization work, trimmed duplicate input/q validation,
and explicitly selected `spawn` for both process pools. It retained the frozen
scientific configurations and historical evidence. These source changes make
the prior canaries historical: **route selection requires fresh canaries
against the final source**. Preserve the old logs/receipts when
restarting; do not rebind their hashes to new code. No canaries or production
were launched during the sweep.

Barry resumed Goal051 on 6 September. Both hosts now have fresh canaries from
`ab7e369`, launched at 00:17–00:18 AEST in the sessions above; both initial CPU
processes were verified active. The old canary directories were preserved.
Linux passed 54 portable tests, and both live input plans produced identical
identities. The exact current paths and archive names are in the runbook.
At the 13:04 AEST wake-up, Mac had completed and its five-receipt evidence
validated. Deep-server rebooted at 03:31 after one serial receipt, interrupting
its batch. The interrupted directory was preserved and a fresh server batch
started at 13:05:09 AEST from unchanged source; its CPU process was verified
active.

At the 8 September wake-up, deep-server had completed at **19:06 AEST on
6 September**, exit 0, with all ten receipts. Both host summaries reproduced
exactly; independent checks covered transfer hashes, timing, interval
concurrency, convergence, identities, and zero ecological metrics/outer access.
The selected route is **Mac mini, three workers**: measured throughput was
5.82 canary probes/hour versus 3.81 on deep-server at eight workers. The server
measurement reflects substantial background contention, not an intrinsic
hardware ranking. The route receipt is `metadata/goal051_canary.json`.

Production launched locally at **09:22:38 AEST on 8 September**, in tmux
`dsdm-goal051-conventional`, from unchanged implementation source `ab7e369`.
Barry subsequently requested offloading this multi-day run to Nectar so the Mac
remains available for local work. The Mac process was deliberately stopped
(exit 143), preserving **13 complete q surfaces**; no target endpoint had
started. All 13 checkpoints pass unchanged on Nectar.

Nectar is now ACTIVE at `c3.3xlarge` (64 vCPUs, 128 GiB allocated RAM), with the
working clone at `/data/codex/repos/dSDM` via `nectar-codex-ts`. The execution
plan uses **16 single-thread workers**, an exact VM UUID/capacity check, and
two serial plus 16 concurrent metric-free probes. The new execution module and
config have their own identity; the original scientific source/config hashes
and Mac/deep-server evidence remain unchanged. This is an authorized change of
compute route, not a new scientific protocol.

`scripts/goal051_nectar_launch.sh` chains the Nectar canary, route receipt,
live-host/evidence gate, and unchanged resumable production launcher. The
session is `dsdm-goal051-nectar`, launched at **10:51:23 AEST on 8 September**
from `5404fc6`. The first serial canary process was verified active at 99.9%
CPU. Its execution log/exit files are
`nectar-execution.log` / `nectar-execution.exit` in the Goal051 private root;
production still writes `run.log` / `run.exit`. See the runbook for launch and
restart details. Goal051 remains incomplete until its full evidence passes
acceptance.

At the **14:15 AEST, 8 September** scheduled check, all 18 Nectar canary probes
had completed and the chain had started production at **14:03:04 AEST**.
The 18 receipts, summary and new route were copied back with all 20 SHA-256
hashes verified. Summary/route reproduction and independent checks of timing,
concurrency, convergence, identity and zero outer access passed. The new route
is `metadata/goal051_nectar_route.json`. Measured mixed throughput was 13.48
probes/hour, 2.32 times the Mac's three-worker rate. Production had 20/150 q
surfaces complete, no target endpoints yet, and all 16 workers active with
about 104 GiB available memory. No restart was needed.

At the **17:16 AEST** follow-up, 112/150 q checkpoints passed their original
load/convergence/identity checks (42 q20, 38 q80, 32 qfull); no target endpoint
had started. All 16 workers remained active and checkpoints were still being
written. However, `run.log` had not advanced since 14:53 AEST. The executor
can defer a raised worker exception until queued work finishes during pool
shutdown. This is a suspected pending failure, not a confirmed traceback:
inspect the eventual log/exit and missing surfaces before restarting or
amending anything. Leave the productive workers running meanwhile.

**Current state at 20:17 AEST: stopped for numerical-policy review.** The
pool finished at 18:49:53 AEST with exit 1. Its first reported exception was
`q_linear_nonconverged_after_extended_attempt`: both 5,000 and 10,000 iteration
ceilings were exhausted with `ConvergenceWarning`. No target endpoints or
ecological scores were generated. All 143 completed q checkpoints validate;
the seven missing surfaces are all full-auxiliary: block1/folds0,4;
block7/folds0,2,4; block8/folds0,4. The original executor did not attach a
surface ID to the reported error or retain every individual exception.
Preserve this distinction; do not label all seven with the single traceback.

The 286 model/receipt files and four execution logs/exit markers were returned
to private `nectar-return-20260908T1017Z` under the Goal051 root, with all 290
SHA-256 hashes verified. Both the remote checkpoints and stopped Mac logs are
preserved. Compact evidence is
`evidence/seawfb_conventional/goal051/q_stage_failure.json`. Do not repeat the
unchanged failed schedule or relax convergence without explicit authorization
for a versioned numerical amendment. Nectar currently has no active compute.
The reviewable recommendation is
`docs/goals/051-seawfb-conventional-benchmark/Numerical-amendment-3-proposal.md`:
one from-scratch 20,000-iteration tertiary attempt, unchanged objective and
tolerance, with explicit provenance and a strict all-150 convergence gate.
It remains a proposal. The three-hour follow-up stays active but silent while
this reported blocker is unchanged. Nectar remains at c3.3xlarge pending the
campaign decision; no resize or amended fit has occurred.

**Latest: protocol v4 recovery launched on Nectar at 23:19:09 AEST, 8 September.** Barry
approved the complete bounded recovery proposal. Use the fresh-collection
fallback: preserve all v3 evidence and rerun 150 q surfaces in
`data/processed/dsdm/goal051-seawfb-conventional-benchmark-v4`. The initial
Nectar chain first runs the isolated block1/fold0/full stress fit, then repeats
two serial/16 mixed metric-free canaries and writes
`metadata/goal051_nectar_route_v4.json`. Only then may q production start; all
150 must validate before any target endpoint is scheduled. Every q failure is
recorded immediately by surface. A final 20,000-iteration failure stops again;
no further numerical amendment is authorized. The old unresolved-approval
paragraphs above are historical. See the current section at the top of the
Goal051 Runbook for v4 paths and continuation commands.
The launch uses source `ce63d96`, with 84 portable tests passed on both Mac
and Linux and the exact v4 input identity validated. The initial detached
stress process is active; convergence and production remain pending. The
three-hour follow-up now explicitly follows the v4 chain. All 290 original
v3 artifact hashes were verified unchanged before and after the remote update.

**02:20 AEST, 9 September:** the isolated stress surface converged at 10,478
iterations on the tertiary attempt after reaching 5,000 and 10,000 on the
first two attempts. Both returned artifacts match remote hashes; standard
receipt replay and independent checks of identity, seed, attempt sequence,
parameters, heads, exclusions and weights passed. Compact evidence is
`evidence/seawfb_conventional/goal051/amendment3_stress.json`. The first of two
serial canaries is complete and the second is active; the mixed batch and
production remain pending. Keep the existing chain running.

**05:20 AEST, 9 September:** all 18 v4 Nectar canaries passed and the existing
chain started fresh q production at 03:49:44 AEST. All 20 returned canary,
summary and route hashes match Nectar; the summary and route reproduce
exactly, and independent interval/concurrency, convergence, identity and
digest checks passed. The current route is `metadata/goal051_nectar_route_v4.json`.
All 43 completed q surfaces validate (19 q20, 16 q80, eight qfull); all 16
workers are active, with no failure receipt or exit marker. Target endpoints
have not started. Continue the existing q stage; do not change its source.

**08:20 AEST, 9 September:** 136/150 q surfaces now validate: all 50 q20,
46 q80 and 40 qfull. Two formerly unresolved full surfaces (block1/folds0,4)
converged on the tertiary attempt at 10,478 and 10,267 iterations. The other
five formerly unresolved full surfaces are still pending, alongside nine
block9 surfaces. There are no failure receipts or exit markers; workers remain
active and no target endpoint has started. Continue the existing chain.

**11:21 AEST, 9 September:** all 150 q surfaces are complete and independently
verified (50 per auxiliary size; 61 primary, 82 extended, seven tertiary).
All seven formerly unresolved full surfaces converged at 10,194–10,553
iterations. Returned all 300 model/receipt files with verified hashes and
replayed the complete q provenance gate on the Mac. Independent parameter,
seed, attempt, head/exclusion and weighting checks passed; compact evidence
is `evidence/seawfb_conventional/goal051/q_v4_acceptance.json`.
Target fitting completed at **16:15:47 AEST on 10 September**: all 303
endpoints and 449 q conditions are present, with all five families available
at every endpoint. Aggregation passed at about 17:30 AEST and the existing
chain is running final `validate --complete` (PID 23216 at 17:46 AEST).
All 606 endpoint files were returned to the Mac with verified SHA-256 hashes;
the aggregate was returned privately as `summary-returned.json` in the v4 root.

The independent endpoint audit passed all 6,763 prediction groups and
474,174,113 rows, with maximum metric difference 4.45e-16. Candidate/family
selection, q reuse, fit counts, coverage and q provenance passed. See
`evidence/seawfb_conventional/goal051/independent_endpoint_audit.json`.
The 49 rejected candidates are all `enet08` nonconvergence; three elastic-net
candidates remain everywhere. Rejections are more frequent in the lowest
prevalence quartile (18/75 versus 4/75 in the highest), reducing tuning breadth,
although the frozen family-availability gates pass at 100%.

**12 September: Goal051 is accepted.** Barry approved proceeding autonomously
under the recommendation to retain the original family-level coverage gate
and explicitly document the prevalence-patterned `enet08` candidate failures.
No refitting or post hoc numerical/gate change occurred. All 303 endpoints,
449 q conditions and 150 q surfaces passed native and independent verification;
results are returned with verified hashes. The accepted aggregate and bound
receipt are `evidence/seawfb_conventional/goal051/summary.json` and
`completion_review.json`. The detailed limitations and results are in the
Goal051 Decision record.

Nectar remains parked at c3.xsmall with all evidence preserved. The completed
Goal051 heartbeat `check-dsdm-nectar-progress` is paused. Do not restart its
production chain or repeat heavy validation on the parked VM.

The current task advances the prospectively frozen Goal052 comparison through
implementation and validation under Barry's autonomy request. Its original
config is preserved byte-for-byte as the scientific freeze; execution status
and authority are recorded in the Goal052 Decision/Runbook. The runner and
43 focused tests pass on Mac and deep-server. CPU foreach AdamW passed
within-host bitwise stopping/replay comparisons on both machines; fused AdamW
is deferred because it changed Linux numerics. Source `e309ca8` is staged on
deep-server. Its fresh two-worker canary passed at 14:37 AEST, with bitwise
repeat agreement and maximum worker RSS 2.545 GiB. The full-row profile also
passed: 79.54 minutes for auxiliary pretraining and 2.395 GiB peak RSS. Returned
receipt hashes and fit invariants are verified. The approved 24-hour pilot
stopped at 16:28 AEST on 13 September with exit 124; no pilot workers remain.
Two block-0/fold-0 pretraining checkpoints are verified and preserved:
bridge_wide took 11.97 hours (33 discovery, selected/replay 3), bridge_control
15.44 hours (34 discovery, selected/replay 4). Deeper fits were interrupted;
no target leaves, architecture selection or ecological metrics were generated.
See `docs/goals/052-seawfb-dsdm-experiment/PilotReview.md` and the tracked
`pilot-review.json`/`pilot-closeout-manifest.json` evidence. The four-hour
follow-up resumed for the subsequent 48-hour/eight-worker continuation.
The latest state at the top of this handover and `PilotReview.md` describe it.
Outer outcomes remain sealed. Routine implementation and tests can proceed;
material scientific amendments require discussion. Compute allocations now
fall under Barry's standing authorization. Start from the current Goal052 runbook and
live source/test state, not the historical Goal051 launch paragraphs above.

## What Follows

Goal 052's separate dSDM design was frozen before Goal 051 ecological scores:
target-only random-init residual MLP, target-plus-q MLP, pretrained frozen
trunk, and full fine-tuning; auxiliary sizes 20/80/full and five paired seeds.
A bounded four-architecture panel selects one shared architecture using
training-only evidence. Do not redesign it after seeing conventional scores.

Goal051 is now accepted and Barry has authorized autonomous continuation.
Its [v4 config](config/goal052_seawfb_dsdm.json) records
all three numerical amendments. A later, separately authorized bird outer
evaluation precedes cross-case synthesis and manuscript rewriting.

## Working Contract And Practical Guardrails

- Read the current global `~/.codex/AGENTS.md` and any repo-local instructions
  present on arrival. There was no repo-local AGENTS.md at this handover.
- Use [Twilight Laboratory](/Users/bwbrook/.codex/skills/twilight-laboratory/SKILL.md)
  for scientific programme design, autonomy, delegation, and stopping, and
  [Kill Your Darlings](/Users/bwbrook/.codex/skills/kill-your-darlings/SKILL.md)
  to keep implementation and validation lean, not to trigger another broad audit.
- Be Barry's assertive research colleague. Decide routine reversible matters
  and accept/commit/push completed in-scope work after focused review. Consult
  him for consequential science, privacy, strategic, or resource trade-offs.
  Report ecological meaning and a substantive next tranche at meaningful
  endpoints, not an approval request per small step.
- Follow **rigour at the scientific decision boundary; proportional
  engineering everywhere else**. One focused review and material repair is
  normal; stop when more polish will not change the decision. Avoid compatibility
  paths, ceremonial ledgers, and repeated tests for old behaviour.
- Use `uv run --locked` with the Python 3.12 environment. Main implementation
  lives in `src/dsdm_phase1/`; current runner is
  `goal051_seawfb_conventional.py`, sharing `seawfb_modeling.py`.
  Use focused gates for current changes. Historical broad-suite failures are
  separately recorded debt, not a reason to loop through unrelated repairs.
- `tas_cam/` is Barry's authoritative private camera dataset and must remain
  untracked. Keep raw records, precise locations, camera identifiers,
  row-level predictions, and bulky outputs private under ignored paths.
  Commit compact aggregate evidence and provenance, not raw payloads. Camera
  nondetections are **survey-supported absences**, not unsampled-cell zeros.
- For long compute, use detached tmux, verify launch, provide status commands,
  then stop until Barry wakes the task. Consult the `nectar` control-plane docs
  under `/Users/bwbrook/work/nectar` before a new resource decision. Do not
  assume GPU access or superiority; use workload-specific evidence.

Read next only as needed: the [strategic roadmap](docs/strategic_plan_30000ft.md)
for rationale (not current status), [Goal 050 decision](docs/goals/050-seawfb-modeling-foundation/Decision.md)
for foundation semantics, and [Goal 051 goal](docs/goals/051-seawfb-conventional-benchmark/Goal.md),
[log](docs/goals/051-seawfb-conventional-benchmark/Log.md), and runbook for
continuation. There is no need to ingest Goals 001-052 wholesale.
