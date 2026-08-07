# Log

## 2026-08-07 - Design freeze

- Barry approved splitting real-data binding and compute calibration from the
  long architecture-selection run.
- The orchestrator froze the local sealed-foundation adapter, independent
  de-identified remote trainer, 77-column target schema, reserved 78th `q`
  column, rotating stopping fold, exact reset/replay lifecycle, and three
  concrete calibration cases.
- The bounded workload is 24 logical evaluations and 48 physical fits. The
  later architecture selection is 1,440 logical evaluations and 2,880
  physical discovery/replay fits.
- Canary runtime is isolated Python 3.12, NumPy 2.2.6, and PyTorch 2.7.1;
  Mac/deep-server use CPU wheels and Alien uses the official cu118 wheel with
  driver 546.01. The repository lock remains unchanged and Goal033 must freeze
  production runtime separately.
- Goal032 stops with a compute recommendation. No architecture search, real
  outer access, ecological metric, long `tmux` run, or dependency change is
  authorised. Implementation workers must not commit or push; after acceptance
  gates pass, the orchestrator may publish under Barry's standing authority.

The implementation evidence, host receipts, review findings, and final
recommendation are recorded below.

## 2026-08-07 - Implementation and real binding

- Added a local-only adapter around the sealed Goal029 foundation and an
  independent de-identified trainer. The adapter verifies Goal029 plus both
  Goal026 authorities before materialising any case.
- Exported three content-addressed bundles with 77 predictor columns and no row
  identifiers, coordinates, raw products, held-fold labels, or outer material.
  The final digests are `0d4a9173...` (light), `a8848403...` (medium), and
  `f61b5cb...` (heavy); all bind the exact Goal032 config and report outer
  attempted/open `0/0`.
- Implemented earliest-strict-minimum stopping, deterministic CPU-generated
  epoch permutations, exact reset/replay, finite-value gates, CPU/CUDA runtime
  witnesses, and one fixed process per GPU for the conditional Alien
  concurrency path.

## 2026-08-07 - Calibration, review, and acceptance

- Completed 18 serial logical evaluations across Mac CPU, deep-server CPU, and
  Alien CUDA, followed by the six-task Mac-only concurrency panel: 24 logical
  evaluations and 48 discovery/replay fits in the accepted inventory.
- All repeat and Mac cross-panel semantic/model/prediction digests agree. Every
  host used the same bundle per case; swap growth and outer attempted/open were
  zero.
- Serial throughput was 1.854 logical evaluations/s on Mac, 0.340 on
  deep-server, and 0.153 on Alien. The three-worker Mac panel took 2.698 s.
- The central Goal033 projection is 647.45 s (10.8 min); the conservative
  300-discovery-plus-300-replay ceiling is 12,274.95 s (3.41 h). Selected-host
  peak RSS was 285,212,672 bytes with 24,914,165,760 bytes of worker-adjusted
  RAM headroom.
- The focused independent review found and closed authority-file verification,
  bundle-inventory validation, cross-panel determinism, host-attestation,
  memory-reporting, and conditional CUDA-scheduling gaps. The tracked receipt
  validates against the private rows and sibling bundles. The final independent
  verdict was supported with no remaining P0/P1 findings. Goal032 stops here;
  no architecture search, `q` fit, ecological metric, long `tmux` job, or
  outer assessment access occurred.
