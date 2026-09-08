# Goal 051 log

## 2026-09-05 - prospective authorization

- Authorized the SEAWFB five-family conventional benchmark on the Goal 050
  retained training substrate.
- Preserved the 157-target scope, 73-target 25/50/100% ladder, 84 full-only
  targets, five frozen spatial folds, X10 support rule, natural prevalence,
  and strict outer firewall.
- Froze Goal 052's separate dSDM protocol before exposing Goal 051 ecological
  scores. No model fit, score, outer outcome, or production run is recorded in
  this protocol log.

## 2026-09-05 - numerical amendment 1

- A metric-free canary exposed primary `q_linear` SAGA nonconvergence before
  any ecological score was calculated.
- Authorized a numerical-only amendment: tolerance 1e-5, primary ceiling 5,000
  iterations, then one from-scratch retry at 10,000 iterations with the same
  seed if the primary attempt warns or reaches its ceiling.
- Acceptance still requires convergence. Ceiling-stability acceptance remains
  deferred. Solver, C, l1 ratio, rows, weights, features, exclusions, and seed
  are unchanged. No ecological score or outer outcome informed this amendment.

## 2026-09-05 - convergence blocker after amendment 1

- Repeated the metric-free canary at protocol version 2 from commit `c030674`
  on `Barrys-Mac-mini.local` and `deep-server`.
- Both hosts exited 1 during the first serial canary with
  `q_linear_nonconverged_after_extended_attempt`. Neither host produced a
  canary receipt or reached the mixed-concurrency stage.
- The one prespecified numerical repair pass is exhausted. Compute-route
  selection and production remain unlaunched pending an explicit decision on
  a different q-linear convergence policy or model.
- No ecological metric was calculated and NCP, SEH, and NNC remained sealed.

## 2026-09-05 - numerical amendment 2

- User-approved a numerical-only correction before any ecological scores.
- The q solver now divides collapsed sample weights by `k = max(weight)` and
  uses `solver_C = canonical_C * k` (`canonical_C = 0.1`), preserving the exact
  penalized likelihood up to the common factor `1/k`. Rows, equal-total head
  weighting, features, exclusions, and seed are unchanged.
- Convergence is classified from `ConvergenceWarning`; unrelated warnings are
  recorded, while explicit numerical warnings and iteration ceilings remain
  rejection conditions. Deprecated q `penalty` and `n_jobs` arguments are
  removed. Receipts bind `k`, canonical and solver `C`, representation, and
  warning types. No ecological score or outer outcome informed this amendment.
- Focused verification passed: `31 passed`; the weighted penalized objective
  equivalence and practical probability equivalence tests passed; `bash -n`
  and `git diff --check` passed. Protocol-v2 failures did not retain per-attempt
  iteration or warning-type details. Inspection now confirms that deprecated
  sklearn arguments could emit warnings falsely captured by `bool(caught)`, so
  those failures alone do not prove exhausted-iteration nonconvergence. Prior
  v1 history remains intact.

## 2026-09-05 - detached corrected canary handoff

- Correction `c14bc47` is committed and pushed cleanly on Mac and deep-server;
  the independent focused rerun remains `31 passed`.
- The corrected protocol-v3 canary-batch was launched at approximately 16:27
  AEST under the existing approval: Mac session `dsdm-goal051-canary-mac` in
  `/Users/bwbrook/papers/dSDM`, with `canary/batch-v3-mac.log` and
  `canary/batch-v3-mac.exit` relative to the private run root;
  deep-server session `dsdm-goal051-canary` in `/data/codex/repos/dSDM`, with
  `canary/batch-v3.log` and `canary/batch-v3.exit` relative to the private run
  root.
- At approximately 16:32 AEST both CPU processes were active. The first
  receipt had not completed; no failure, outer access, or ecological metric
  was observed. Prior logs were preserved. The main benchmark remains
  unlaunched.
- User cadence is detached long compute followed by wake-up. On resume, finish
  valid two-host summaries, run route selection, then launch the full
  production benchmark under the existing approval. No new permission is
  required.

## 2026-09-05 - bounded code and test simplification

- The successor inspected the detached jobs: Mac completed all five receipts;
  deep-server completed two serial receipts then failed in mixed concurrency
  with PyTorch's autograd/fork threading error. Production had not started.
- Under Barry's requested code sweep, removed the caller-free Goal029 P-spline
  experiment and its authority registry/tests. Retained Goal028's pyGAM path,
  the accepted model families, historical evidence, and frozen configurations.
- Q preparation now evaluates training q once per role pair instead of three
  times, preserving exact values and training-only standardization. Removed
  unused helpers/arguments, duplicate CLI input validation, and repeated q
  checkpoint loads in complete validation. Full metric replay remains intact.
- Both process pools explicitly use `spawn`. A real two-worker synthetic
  backward-pass test runs after parent autograd initialization. Linux canary
  verification is still pending; no remote code or jobs were changed here.
- Removed private-file dependencies from the Goal049 authority and Goal051
  inventory unit fixtures. Consolidated duplicate Goal050 happy-path checks
  into explicit `real_scope` replay tests. Older unmarked historical test
  assumptions and the aggregate/final-validation replay overlap remain deferred.
- Focused final gate: **56 passed, 3 real-scope checks deselected in 5.33 s**.
  This covers the README's five-file gate plus the existing canonical-runtime
  and missing-pyGAM isolation checks. Canonical candidate definitions and
  neural training/serialization are structurally unchanged; exact q values,
  convergence, exclusion, tamper detection and all-endpoint replay checks pass.
- README and handover now describe the current scientific and execution state.
  No data, ecological scores, source-binding receipts, or lockfiles changed.
  Source changes invalidate the old canaries for route selection: retain them
  as history and run fresh two-host evidence after continuation. No canaries,
  production, or ongoing monitoring were launched during this sweep.

## 2026-09-06 - resumed corrected two-host canaries

- Barry authorized continuation of Goal051 under Twilight Laboratory. Kept the
  frozen Goal051/052 science and the existing detached-compute cadence.
- Confirmed no Goal051 jobs remained active; fast-forwarded the clean
  deep-server checkout from `c14bc47` to `ab7e369`. Local source was already
  clean at `ab7e369`.
- Both live input plans passed with identical identity fields, including
  source SHA `d304b3a9bfea3b5e7bbffc8fe3ea1ddce050fadfa0248a05a768389e462fb28b`.
  The Linux portable gate passed **54 tests, 3 real-scope tests deselected**,
  including actual spawned-worker backpropagation after parent autograd.
  Two existing warnings concerned the unused Quadro K620 CUDA architecture;
  the computation uses CPU.
- Deep-server had 64 logical CPUs, 117 GiB available memory and 4.4 TiB free
  on `/data`. Background load was about 49–51 at launch. Retained the approved
  mixed concurrency of eight; interpret measured throughput in that shared
  load context. Mac had 69% free memory and about 260 GiB free disk.
- Preserved prior canary directories as
  `canary.previous-20260905T141741Z` on Mac and
  `canary.previous-20260905T141805Z` on deep-server. No old receipt was rebound.
- Launched `dsdm-goal051-canary-mac` at 00:17:41 AEST and
  `dsdm-goal051-canary` at 00:18:05 AEST, both from `ab7e369`, with explicit
  one-thread estimator environment and atomic exit markers. Each private
  `canary/launch.sh` retains the exact command. Both CPU processes were active
  at the post-launch check; neither had an exit marker yet.
- No production or ongoing monitor was launched. On wake-up, inspect these
  existing sessions, validate complete host summaries and underlying receipts,
  select the measured route, then proceed to the benchmark under the existing
  approval. Do not duplicate jobs or use the archived canaries to select it.

## 2026-09-06 - wake-up and server reboot recovery

- At 13:04 AEST, Mac had exited 0 with all five receipts. Reproduced its
  summary exactly and independently checked identities, timing arithmetic,
  interval concurrency, q digest stability, accepted convergence attempts,
  and zero ecological metrics/outer access. Mean serial latency was 1,736 s;
  the three concurrent probes completed in 1,855 s. These are canary timings,
  not production estimates.
- Deep-server boot records show a 03:31 reboot into kernel 6.8.0-139-generic.
  The batch left one valid serial receipt (7,450 s under the earlier heavy
  host load), no completed summary, and no exit marker. Its accepted q fits
  converged at 1,263 and 9,566 iterations. No new model failure was observed;
  the reboot cause was not investigated or changed.
- Preserved the interrupted directory as
  `canary.interrupted-20260906T030509Z` and restarted the complete deep-server
  batch at 13:05:09 AEST from unchanged `ab7e369`. Current host load was about
  1–2 with 122 GiB available memory. A fresh timing batch avoids combining
  serial measurements across the reboot and substantially changed host load.
- Verified the restarted CPU process active. Retained the completed Mac run.
  Route selection and production remain pending the server's full evidence;
  no ongoing monitor or duplicate job was created.

## 2026-09-08 - canary acceptance and production launch

- Deep-server completed at 19:06 AEST on 6 September, exit 0, with two serial
  and eight concurrent receipts. The repaired spawned-worker path completed.
- Transferred ten receipts and the host summary privately to Mac; all eleven
  SHA-256 hashes matched the server originals. Both summaries reproduced
  exactly. Independent arithmetic and receipt checks confirmed serial order,
  mixed interval peaks of three/eight, throughput, peak RSS, matching source
  identities, accepted convergence, within-host q parameter stability, and
  zero ecological metrics/outer access. Cross-platform bitwise equality is
  not asserted.
- Selected Mac with three workers and wrote `metadata/goal051_canary.json`.
  Mac mixed throughput was 5.822 probes/hour versus deep-server 3.815
  (1.526 times faster). Mean serial latencies were 1,736 and 7,063 seconds.
  Deep-server experienced substantial background load during the run; this
  is a measured operating-route choice, not a hardware ranking or production
  ETA. Mac preflight showed 69% free memory and 253 GiB free disk.
- Launched `dsdm-goal051-conventional` locally at 09:22:38 AEST using the
  existing resumable launcher and three workers. Implementation source and
  frozen Goal051/052 configurations are unchanged. The launcher runs input
  validation, 150 q surfaces, 303 target endpoints, aggregation, and complete
  validation. Input validation passed and all three spawned q workers were
  verified active at about 99.5% CPU each. Production acceptance remains pending.

## 2026-09-08 - user-directed Nectar offload

- Barry preferred a resized Nectar VM for this multi-day workload to preserve
  Mac Mini capacity. Stopped the Mac q processes deliberately; exit 143 is an
  operator interruption. Preserved and validated 13 complete q surfaces. No
  conventional endpoint had begun.
- Installed OpenStack CLI on Mac and, with Barry's explicit authorization,
  copied the existing credential files privately from the briefly awakened
  MacBook. Resized idle Nectar from `c3.xsmall` to `c3.3xlarge`; OpenStack is
  ACTIVE with 64 vCPUs and 128 GiB allocated RAM. Guest/storage/service checks
  passed. Infrastructure details are in the `nectar` control-plane repo.
- Staged source using a Git bundle and transferred only the retained-training
  inputs plus the 13 q model/receipt pairs. All 30 private files matched their
  Mac SHA-256 manifest. The unchanged input plan and all 13 checkpoint loads
  passed on Nectar. The locked environment and caches live under `/data`.
- Added a separate execution adapter/config for the exact Nectar VM and 16
  workers. It repeats the original metric-free numerical probe using frozen
  scientific helpers, validates two serial/16 concurrent receipts, and binds
  their hashes plus its own execution identity. The production gate replays
  raw evidence and checks the live host. Existing science source/configs and
  prior canary/route receipts retain their original hashes.
- The first Linux gate passed 72 tests with three real-scope checks deselected.
  Parent review added a wall-clock/interval consistency check before launch.
  The final 19 Nectar-specific tests passed on both Mac and Linux, and the
  live Nectar identity/capacity gate passed. The launcher passes its shell
  syntax and ShellCheck gates. It will chain
  validated Nectar canary evidence into the unchanged resumable production
  launcher; scientific acceptance remains pending.
