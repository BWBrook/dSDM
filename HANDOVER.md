# dSDM: Fresh-Task Handover

Prepared for Barry Brook's successor research collaborator, 2026-09-05.
Repository: `/Users/bwbrook/papers/dSDM`. Original handoff followed `8be8ec6`;
execution status was refreshed on 2026-09-08 for the move from Mac production
to resized Nectar at Barry's request.

## Current handoff — 26 September, Goal052 computational acceptance passed

Barry reported the completion email. PBS **812164.kunanyi-ohpc** finished
**F / exit 0 at 01:41:50 AEST on 26 September**, after **3h57m59s** on n001
(one CPU; 2.140 GiB peak memory). The unchanged native independent replay
returned **`goal052_complete_valid`**: **900 pretraining lifecycles, 42,345 unique
target lifecycles and 449 conditions**, with zero outer-response rows read.
No PBS jobs were active at the 26 September return check.

The exact accepted summary and native completion marker are now local.
The 5.37 MB return archive and all 16 contained evidence-file hashes passed;
87 local checks verified the launch/helper/source/input/q bindings, receipts,
condition inventory, preserved selection and byte-identical canonical imports.
All previously returned fits remain preserved. See
`evidence/seawfb_dsdm/goal052/completion_review.json` and
`docs/goals/052-seawfb-dsdm-experiment/Results.md`.
Accepted summary SHA256:
`ec0bc6c2df8cabd3554f5b2b9eebda97b3426ddd186bfa2acc64ba3d1244a3d3`.
Its native `complete_pending_validation` field is immutable aggregation output;
the separate hash-bound `goal052_complete_valid` receipt confirms acceptance.

**The compute stage is complete.** Next is focused scientific review of effect
sizes, controls and target/block heterogeneity. Keep the daily monitor deleted;
do not restart fitting or validation. NCP, SEH and NNC remain sealed. Outer
evaluation, retained-full refits, mapping and manuscript claims retain their
separate authorization boundaries. Source remains e309ca8 / fce7fb52… .
Correspondence thread 32 message **562** records completion and requests Fable's
focused scientific critique. Keep retrieval cursor **561**, the last contiguous
read checkpoint.

## Historical handoff — 25 September, validation continued after wall-time cap

Barry reported the PBS email and resumed the task. Notification **811800**
exited 0 at **14:24:01 AEST** with `00:00:00` execution time, as expected for
the administrative job released after all production predecessors ended.
All **48 target jobs 811750–811797** finished with exit 0 after **3h22m33s–
3h46m50s** each. Independent review verified all actual-host qualifications,
owners, exits and rank completions: 41,250 final-stage tasks, with the expected
42,345 unique leaf receipts present. Peak sampled RSS was 64.974 GiB during
qualification and 40.578 GiB during production. No fit restart is required.

See `evidence/seawfb_dsdm/goal052/kunanyi-target-completion-review.json` and
private `kunanyi-target-closeout-20260925/`. All 728 returned host-evidence
hashes passed; `host-review.json` records 1,129 successful checks. Source,
launch and driver bindings remain unchanged. All 42,345 leaf pairs are now
hash-verified and imported locally; native scientific acceptance is still pending.

Transfer-only PBS **812035** finished with exit 0 after **4m09s**, packaging
all 42,345 pairs into eight archives (5.83 GB). Remote package and hashes:
`/u/bwbrook/codex_kunanyi/dsdm-goal052/target-closeout-20260925/parallel-leaves`.
The slow serial collector was stopped, preserving its completed host archive.
All eight archive hashes and all 84,690 file hashes passed. The canonical local
`leaves/` now holds every pair: 40,885 new pairs plus all 1,460 unchanged screen
pairs. Private `import-review.json`, `leaf-file-hashes.json` and the preserved
archives bind the return; no download or import process remains active.

Initial validation **812145** exited 1 after 18 seconds: the audit helper assumed
`SCRIPT.parents[6]`, which fails in the shorter remote path. It stopped at
helper import, before leaf audit or aggregation. Preserve that failed attempt
and `kunanyi-validation-first-attempt-review.json`. The fix uses the current
working directory as the fallback while the caller supplies the exact root.
A shallow-path import test and all 1,460 preserved screen receipt-contract
checks passed; no fitting code changed.

Validation **812148** reached its four-hour wall-time cap and PBS terminated
it with exit **271** after **4h01m38s**, at **19:14:59 AEST**. Its output explicitly
records the wall-time kill; the old shell EXIT receipt misleadingly says 0 and
must not override PBS or native acceptance evidence. Memory peaked at only
2.97 GiB. The complete 42,345-leaf audit **passed at 17:31:15 AEST**, after
2h17m54s; the job then entered aggregation. No summary or native completion
was produced. See `kunanyi-validation-timeout-review.json` and private
`validation-v2-closeout/leaf-review.json` (SHA256
`ab0d2d4247b095d0a0992000c0f3438b3ddcbf89e58847caa97c18416152cfdf`).

Continuation **812164.kunanyi-ohpc** (`ds052_accept`) started at **21:43:51
AEST** on the same **n001** host and SIF, one CPU / 16 GiB / **24 hours**, with
PBS end/abort email to Barry and rerun disabled. Requested cap: **26 September
21:43:51 AEST**, subject to PBS termination handling. Work directory:
`/u/bwbrook/codex_kunanyi/dsdm-goal052/validation-continuation-20260925`.
Immutable `validation-launch.json` SHA256:
`4553390e694c3c0c6c8422db04c6c4e84a0707c83b17c3acc9dd9e99df240d87`.
It rechecks all saved-fit hashes, accepted inputs, source, manifest and prior
audit bindings before reusing the passed full-leaf audit. It then calls the
unchanged native aggregation and independent `validate_outputs`. No fits are
rerun. A native run lock excludes competing schedulers; durable `progress.json`
and `validation.log` expose phase and completed fold-group progress. Explicit
termination handling passed success/failure/SIGTERM tests; independent review
found no blocker. Startup verified PBS R on n001, no exit receipt, and progress
in `rehash_completed_audit_inputs` after source/runtime checks passed. See
`kunanyi-validation-continuation-review.json`.

**Wait for Barry's PBS email and resumption.** Inspect existing **812164**,
`progress.json`, `validation.log`, `wrapper-exit.json`, `phase-exit.json` and
`native-validation.json`; retrieve `validation-return.tar.gz` when present.
Require successful PBS termination and native acceptance. Do not resubmit
blindly or recreate polling. Scientific acceptance remains pending. The saved
900 pretraining and 42,345 target pairs remain intact locally and remotely.
No sealed access, full refits, maps, manuscript claims or scientific amendments.
Correspondence thread 32 message **560** records this continuation; keep retrieval
cursor **554**, the last contiguous read checkpoint.

## Historical handoff — 25 September, 48 target nodes; PBS completion email

Barry restored TPAC access. All old jobs **811265–811289.kunanyi-ohpc** finished
with exit 0, exact rank completions and accepted actual-host qualifications.
All **900 pretraining checkpoint pairs** are verified and preserved locally,
including 535 new pairs since 23 September. See
`evidence/seawfb_dsdm/goal052/kunanyi-pretraining-completion-review.json` and
private `kunanyi-check-20260925/`. Preserve these accepted audits rather than
repeating the historical checks. The completed `production-20260923` root and
its original source/driver/launch bindings remain intact; the deep-server
Goal052 scheduler remains stopped.

Preparation **811744.kunanyi-ohpc** exited 0 after verifying the fresh import
of 900 checkpoint pairs and 1,460 screen leaves and reproducing the native
final-target manifest. The sole active fitting allocation is **811750–811797.kunanyi-ohpc**,
48 fixed shards (`node-000`–`node-047`), each 28 single-thread workers, 110 GiB
and 48 hours. At **25 September 10:37 AEST**, all 48 jobs were running on distinct
hosts with no observed exit. Their original caps are **27 September
10:37:06–10:37:11 AEST**. PBS R is startup evidence;
each actual host still must pass exact canary/full-profile/resource qualification
before fitting. No new target-host qualification or target leaf is accepted by
this initial snapshot. A final 10:42 AEST startup check still found all 48
running and no exit receipts.

Canonical root: `/u/bwbrook/codex_kunanyi/dsdm-goal052/targets-20260925`.
See `evidence/seawfb_dsdm/goal052/kunanyi-target-launch-review.json` and private
`kunanyi-target-staging/` for exact preparation, launch, returned PBS records
and independent review. Immutable `handoff/target-launch.json` SHA256:
`4aeedc0d4e426dfee7d2c2d7f7fe08d686611bd46b3fecbcc606b5967e3177a7`.
Final-target manifest digest:
`5d54bd7cdeb8368ec4ca024cc6a853a4b2e3268ec9bc6cbf49fb8e1a76764cc6`.
The 900-checkpoint barrier and exact 1,800-file inventory are bound in the launch.

There are **41,250 final-stage tasks**, with **365 cached screen fits** and
**40,885 new fits**. Require all **42,345 unique target leaves** before any
aggregation. Within `.goal052-pbs/`, inspect `dispatch-targets-20260925`,
`jobs/JOBID`, `qualification/JOBID/qualification` and
`final_targets/{ownership,completions}`. Never rerun the dispatcher blindly, duplicate ranks,
reset a live deadline, change active drivers or clear ownership before verified
stopped-job recovery. Qualify any changed allocation/runtime before restarting.

External launch changes are **e70fd46**; frozen fitting source remains
**e309ca8 / fce7fb52...**, with accepted data/config/lock/q surfaces unchanged.
Barry has replaced the daily monitor with **PBS completion email** because
inactive TPAC portal sessions expire. Automation `continue-dsdm-goal052` was
**deleted**. Do not recreate polling or an automatic wake-up; wait for Barry to
report the email and resume this task.

Notification **811800.kunanyi-ohpc** (`ds052_notify`) is in the expected PBS
system dependency hold, with `afterany` covering every job **811750–811797**.
PBS will email **barry.brook@utas.edu.au** when that notification job ends or
aborts. It becomes eligible after all 48 production jobs end, including error
or time-limit exits, and requests only one CPU / 256 MiB / two minutes. All
predecessors had already started before this dependency was attached. This
signals allocation termination; scientific completion still requires returned
receipts, qualifications and the complete target-grid checks after Barry resumes.

See `evidence/seawfb_dsdm/goal052/kunanyi-notification-review.json`. Remote
notification records are `/u/bwbrook/codex_kunanyi/dsdm-goal052/notifications-targets-20260925`;
local copies are in private `kunanyi-target-notification/`. The production
scripts, job ownership and deadlines are unchanged. No partial-grid scoring,
sealed outcomes, full refits, maps, manuscript claims or scientific/numerical
amendments. Correspondence thread 32 message **533** records this superseding
monitoring decision; next retrieval cursor is **533**.

## Historical handoff — 24 September, TPAC access requires renewal

Today's daily check could not reach PBS: SSH rejected expired MFA admission,
and the portal's Enable Jumpbox SSH link redirected to UTAS Microsoft sign-in.
Chrome then blocked automation because an extension UI was open on that page.
Barry has been asked to complete sign-in, dismiss the extension popup and
enable jumpbox SSH. Current job states, new checkpoints, remaining
qualifications and resource use are **unverified**. The last verified remote
snapshot remains 23 September below; its 365 local checkpoints and review
references are preserved. No allocation, source, ownership or deadline changed.

Once access returns, inspect existing jobs **811265–811289** and retrieve only
new evidence. Their original caps remain **25 September, 11:07:47–17:35:20
AEST**, before tomorrow's daily 17:40 check. Preserve stopped-job recovery and
the 900-checkpoint barrier before final targets. See
`evidence/seawfb_dsdm/goal052/kunanyi-access-20260924.json`.
Correspondence thread 32 has no new messages; next retrieval cursor is 518
(last actual thread message remains 467).

## Last verified handoff — 23 September, 17:44 AEST daily check

Qualification job **810907.kunanyi-ohpc** completed with exit 0 on n234:
56 canary jobs across 28 workers and the full-row profile agree exactly with
the accepted deep-server scientific results. The canary took 2.54 minutes and
the full profile 65.93 minutes. PBS recorded 55.97 GiB peak memory. The old
resource sampler crashed; its empty output is retained, and the replacement
procfs sampler passed a live Linux check. This does not change fitting code.

Handoff job **811257.kunanyi-ohpc** completed with exit 0. The new canonical
root `/u/bwbrook/codex_kunanyi/dsdm-goal052/production-20260923` contains all
272 verified pretraining checkpoints and the preserved selection screen.
All 544 pretraining file hashes match the accepted closeout inventory.
The returned 700-task manifest was independently replayed: 25 disjoint shards,
with 24–26 unfinished fits each (628 total). Deep-server remains stopped.
PBS jobs **811265–811289.kunanyi-ohpc** are all running on 25 distinct hosts,
one fixed shard each, 28 CPUs / 110 GiB / 48 hours. All 25 exact canaries
passed. Fourteen hosts also passed the full-row profile and repaired sampler
checks and claimed their production ranks; eleven were still profiling.
Independent review confirmed all returned numerical and host bindings.

There are **365 verified pretraining checkpoints**, including **93 new pairs**
validated and preserved locally today: **165/700** remaining-pretraining tasks
complete, **535 unfinished**. Every new completion is auxiliary-20, taking
1.31–2.37 hours (median 1.67). Auxiliary-80 and full fits remain in progress;
these early completions do not establish a campaign ETA. Sampled group RSS
peaked at 46.67 GiB in production and 65.17 GiB during qualification, below the
100 GiB qualification limit. No job exit, failure or completed rank was seen.
Source, driver, launch, manifest and selection bindings remain unchanged.
Continue these jobs through their existing caps: **25 September, 11:07:47 to
17:35:20 AEST**, depending on actual PBS start. The daily check falls after the
last cap. See `evidence/seawfb_dsdm/goal052/kunanyi-day1-review.json`; private
`kunanyi-check-20260923/` contains the snapshot, returned evidence and audits.
See `evidence/seawfb_dsdm/goal052/kunanyi-pretraining-launch-review.json` and
`kunanyi-node-qualification-review.json` for launch and pilot evidence.

The immutable launch SHA is `3e04173f2834d3df6857e71386a3f65121d14d6f1c0ed15e4c98f17b056c9ccb`;
manifest digest `21506b03ac8884cd497900cdd985bd93aef7c19ed66cdd3f9b28849aa4cdb0fd`.
Launch, handoff and manifest are under the production root's `handoff/`.
Actual per-job qualification and exit records live in `.goal052-pbs/`.
Inspect existing jobs and receipts; never rerun the dispatcher or clear rank
ownership merely to retry. At completion/failure/cap, verify stopped jobs,
preserve and validate checkpoints, then choose a bounded continuation.
All **900 pretraining checkpoints** are required before final-target dispatch;
all **42,345 unique target leaves** before aggregation. Daily checks remain
**17:40 Australia/Hobart**. Sealed data and scientific boundaries are unchanged.

## Historical handoff — 22 September, daily check

The deep-server allocation ended at its original 17:29:30 AEST cap with
**exit 124**. No Goal052 workers or tmux session remain; the native run lock is
available and no multiprocessing semaphore files remain. All **272 pretraining
checkpoints** are validated and preserved locally, **55 new since yesterday**.
The remaining-pretraining stage completed **72/700**, leaving **628**. All
1,460 screen target leaves and the selected architecture remain unchanged.
Local and remote hashes match for all 544 pretraining files; source,
qualification and launch bindings are unchanged. See
`evidence/seawfb_dsdm/goal052/continuation24-closeout-review.json`.
Do not reset the launch binding or restart its original wrapper. Earlier
counts below are historical.

Kunanyi qualification job **810907.kunanyi-ohpc** remains unverified: access
failed because the SSH admission window expired, and refreshing the existing
Enable SSH page requires a fresh UTAS sign-in. Barry has been asked to sign in
and enable jumpbox SSH. This is an access blocker, not a verified job failure.
After access returns, inspect the existing job and its qualification evidence
before production dispatch. No replacement PBS job or new fitting allocation
has been started. The existing daily heartbeat records this state. See
`evidence/seawfb_dsdm/goal052/kunanyi-access-20260922.json`.

## Historical Goal052 state — 21 September, 18:02 AEST

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

Sixth daily check: all **200 screen-pretraining fits and 1,460 screen target
fits are complete**. The frozen rule selected `seawfb_scale`; independent
screen verification and exact selection replay passed. The runner entered
`remaining_pretraining` automatically, with **17/700** complete: **217 total
pretraining checkpoints**, including 34 new since yesterday, have passed
hash, finite-state, stopping/replay and data-contract checks. The 17 new screen
fits took 12.99–20.36 hours (mean 16.55); the first 17 remaining-grid fits took
1.43–7.18 hours (mean 2.44), reflecting different auxiliary sizes rather than
a comparable throughput estimate. All 24 original workers are alive and busy,
with about 83 GiB RAM available and no swap use. Source/runtime/qualification/
launch bindings are unchanged. Continue the same allocation through its
original cap tomorrow, then verify shutdown and choose the next bounded
allocation. Daily cadence and scientific boundaries remain unchanged. See
`continue24-day6-review.json` and `selection-screen-review.json`. The verified
milestone is on Correspondence thread 32, message 455.

## Historical Kunanyi migration preparation — 21 September evening

Barry identified up to 48 nodes × 28 CPUs / 128 GB and authorized using them.
Kunanyi is now the preferred route for the remaining independent fits, after
runtime qualification and verified production handoff. Deep-server continues
unchanged until its original cap tomorrow. See
[the execution note](docs/goals/052-seawfb-dsdm-experiment/Kunanyi.md).
PBS hardware probe 810868 and container probe 810869 both passed (exit 0).
Kunanyi has GLIBC 2.17; Apptainer successfully runs Ubuntu 24.04 with GLIBC
2.39. Package the exact existing Python/locked environment and require exact
28-worker numerical agreement before production. Use the home staging root
`/u/bwbrook/codex_kunanyi/dsdm-goal052`; scratch upload failed, consistent with
X-ray's recorded quota issue. Numerical qualification job **810907.kunanyi-ohpc** started on n234 at
18:54:28 AEST (28 CPUs,
110 GB, four hours). Its runtime/input/driver checksums passed before dispatch.
Inspect that job at the next daily check. No PBS production fits have started.

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
