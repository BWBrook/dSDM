# dSDM: Fresh-Task Handover

Prepared for Barry Brook's successor research collaborator, 2026-09-05.
Repository: `/Users/bwbrook/papers/dSDM`. Original handoff followed `8be8ec6`;
execution status was refreshed on 2026-09-08 for the move from Mac production
to resized Nectar at Barry's request.

## Start Here

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

## Current Work: Goal 051

The approved conventional benchmark is implemented but not yet accepted.
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

Barry authorized a **three-hour recurring follow-up in this thread** on
8 September, superseding the earlier pause on monitoring. The app automation
is `check-dsdm-nectar-progress`. Inspect the existing Nectar chain, handle
routine interruptions, and continue verification/acceptance when outputs are
ready. Pause the follow-up once Goal051 is accepted. Do not launch duplicate
jobs or start Goal052 without its separate execution authority.

On Barry's next continuation, inspect the existing jobs first using the
[Goal 051 runbook](docs/goals/051-seawfb-conventional-benchmark/Runbook.md),
which has exact log/exit paths. Check Nectar's existing session, current stage,
exit marker, and checkpoint inventory; resume valid checkpoints if interrupted.
Keep the stopped Mac run as history. Goal 050's earlier PyTorch throughput
result did not choose this workload's route.
An exit code or receipt alone is not
scientific acceptance: inspect the emitted evidence and proportionally verify
metrics, exclusions, and coverage.

## What Follows

Goal 052's separate dSDM design was frozen before Goal 051 ecological scores:
target-only random-init residual MLP, target-plus-q MLP, pretrained frozen
trunk, and full fine-tuning; auxiliary sizes 20/80/full and five paired seeds.
A bounded four-architecture panel selects one shared architecture using
training-only evidence. Do not redesign it after seeing conventional scores.

Accept Goal 051 before executing Goal 052, and establish execution authority
at that transition. Its [v3 config](config/goal052_seawfb_dsdm.json) records
both numerical amendments. A later, separately authorized bird outer
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
