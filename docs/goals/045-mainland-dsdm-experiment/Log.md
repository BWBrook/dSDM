# Log

## 2026-08-29 - authorised and calibrated

- Barry approved the prospectively frozen Goal 045 experiment, with an Alien
  availability check and the Mac CPU as the guaranteed fallback.
- Live Tailscale ping and passwordless SSH to `alien-wsl` both timed out. No
  code or data were sent to Alien.
- Bound the four frozen arms, three architecture candidates, exact other-19
  pretraining rule, five final seeds, and Goal 044 learning ladder before any
  production fit.
- Prespecified a one-seed, full-target, primary-arm architecture screen across
  every target and fold; the selected architecture is then shared by all arms.
- The Mac CPU canary exercised 277,571 auxiliary rows, 19 heads, 103 encoded
  features, and all four target arms in 11.76 seconds. Pretraining used 9.23
  seconds; Tasmania access remained `0/0`.
- Six focused tests passed. Production is not complete and no canary metric is
  being used as scientific evidence.
- The repository-wide suite returned 687 passed, 2 failed, and 2 skipped. Both
  failures are the already documented Goal 037 `model_adapters.py` digest
  mismatch introduced by Goal 039; Goal 045 does not touch that historical
  config or module.

## 2026-08-30 - production guard repair

- The first detached production launch exited `1` during architecture
  pretraining after writing 72/75 checkpoints. The failure was an absolute
  `1e-8` equality assertion on mathematically equal per-head weights, not a
  model-fit or data-integrity failure.
- The worst observed relative head-total range across all 75 target-fold-role
  combinations was `1.105e-7`, below two float32 machine epsilons
  (`2.384e-7`). The guard now checks the actual float32 training weights at
  that precision. The weight values and scientific objective are unchanged.
- Added the exact production-scale failure pattern as a regression test. Seven
  focused tests, all 75 live weight patterns, and a repeated real-data canary
  passed. The repaired canary completed in 10.91 seconds, including 8.42
  seconds for pretraining.
- The prior checkpoints will be recomputed under the repaired source identity;
  they are not being relabelled or treated as current evidence.

## 2026-08-30 - production complete and accepted

- The repaired detached run exited `0` after 7,987 seconds. It completed 175
  pretraining receipts, 75 architecture-selection receipts, and 875 final
  fold-seed receipts.
- The shared mainland screen selected `bridge_control` with equal-species mean
  rank 1.4 and first place for four of five targets.
- Across 35 target-endpoint strata, full fine-tuning improved mean AUC by
  0.0094 over matched target-only learning and by 0.0035 over the strongest
  Goal 044 conventional model. The contrasts were positive in 34/35 and 30/35
  strata, respectively.
- At the full-target endpoint, full fine-tuning beat the best conventional AUC
  for all five species; the mean change was 0.0038. The gain is small and is
  retained as mainland development evidence, not geographic-transfer proof.
- The independent validator reconstructed all 35 endpoints and 875 final
  tasks. Seven focused tests passed. Tasmania remained sealed at `0/0`, and
  the tracked aggregate contains no row-level locations, responses, or
  predictions.
