# Decision

## Frozen execution contract

- Target: `sarcophilus_harrisii`; held `fold01`; stopping `fold02`; common
  seed `31031`; architecture `resmlp13`.
- Endpoints: `fraction25/ladder00`, `fraction50/ladder00`, and
  `fraction100/full`, in their authoritative Goal028 order.
- Paths: target-only, legacy pooled transfer, frozen multihead transfer, full
  multihead fine-tuning, target plus q-linear, and target plus q-deep.
- Auxiliary discovery uses folds 00/03/04, stopping uses fold02, and replay
  uses all four non-held folds. Only presences and survey-supported absences
  are eligible.
- Pooled and seven-head neural pretraining each use early-stop/reset/replay.
  The elastic-net q surface is one deterministic weighted fit. These three
  artifacts are reused across endpoints; trained target state is never reused.
- Every target lifecycle uses unweighted BCE, AdamW at `0.001`, batches up to
  128, patience 30, maximum 300 epochs, deterministic float32 algorithms, and
  one numerical thread.
- Shared runtime: Python 3.12, NumPy 2.2.6, SciPy 1.16.3, scikit-learn 1.9.0,
  threadpoolctl 3.6.0, and PyTorch base 2.7.1. CUDA/CPU wheel suffixes and
  device facts are recorded separately from the shared fingerprint.
- The bundle and run receipts bind the exact source path/digest manifest.
  q-linear uses `tol=1e-5` and `max_iter=5000`, and must converge before that
  ceiling without a `ConvergenceWarning`. The earlier `tol=1e-6` contract did
  not converge even at 10,000 iterations; the frozen seed converged in 667
  iterations (1.70 seconds) under the revised numerical contract.

## Evidence boundary

Private evidence may contain inner held-fold labels and prediction digests but
not identifiers, coordinates, source paths, raw camera records, or sealed
outer data. The run records no ecological metric. Goal034 selects a compute
route only after matched real repeats. Legacy and multihead target starts are
explicitly bound back to their replayed auxiliary states, rather than inferred
from method labels.

## D034-01 - Freeze the Mac CPU route

Both Mac CPU and Alien CUDA completed two fully validated, deterministic
repeats against the same bundle, source fingerprint, and shared numerical
runtime. Median complete-sentinel time was 17.7535 seconds on the Mac and
186.7903 seconds on one RTX 2080. Under the intended three Mac workers versus
two Alien workers, the matched sentinel projects 15.782 times the throughput
on the Mac.

Freeze `mac_cpu`, three independent workers, one numerical thread per worker,
and no DDP for the later production lifecycle. The prospective rule was to
retain the Mac whenever it delivered at least 80% of Alien throughput; the
result is decisive, so no concurrency panel is warranted. This is a compute-
route decision only. It neither authorises the 8,840-artifact lifecycle nor
supports any ecological or comparative-performance claim.
