# Decision

## D032-01 - Scientific and data boundary

Goal032 is a real outer-training integration and engineering-calibration gate,
not a model comparison. Goal027's conditional relative-habitat-suitability
estimand remains authoritative. Goal025's outer assessment remains sealed and
must report attempted/open `0/0`.

The local adapter may call
`dsdm_phase1.goal029_production.ingest_production_foundation`, which is the
accepted eight-species foundation. Phase1 remains byte-frozen. The adapter
validates the broker/provider/vault boundary locally and exports only
de-identified arrays required by the three cases. Remote trainers cannot
import Phase1 or inspect repository-private products.

## D032-02 - Fixed 77-column neural schema

Use Goal026's 25 population-z-scored continuous predictors and the full
response-independent vocabulary for the three nominal predictors:

| Predictor block | Columns |
|---|---:|
| Continuous | 25 |
| `soil_class` indicators | 13 |
| `veg_mvg` indicators | 22 |
| `landuse_secondary` indicators | 17 |
| **Target X total** | **77** |

No reference level is dropped and no nominal code is treated as ordinal. An
unseen level maps to the all-zero block and increments a diagnostic count.
The raw scalar `q` column is reserved as column 78 for later work; no Goal032
path fits or appends `q`.

## D032-03 - Rotating stopping fold and replay

For held fold `h`, the next cyclic fold is stopping fold `s`; the other three
folds are discovery data. Reuse Goal026's `cv_h` transform for discovery,
stopping, exact-epoch replay, and held-fold prediction. This exposes no
stopping labels to preprocessing, but it does use the predeclared four-fold
training-map covariate transform. That limited transductive convention is
accepted because it is response-independent, already frozen for Goal028, and
common to every architecture. Adding five nested transforms would provide
little decision-relevant gain and would break alignment with the conventional
workflow.

Fit discovery data with full stopping-batch BCE, maximum 300 epochs, patience
30, `min_delta=0`, and the earliest strict minimum. Reset the identical initial
state and replay all four training folds for exactly the selected epoch count
before held-fold prediction. The held fold never sets epochs or weights.

Use batch size 128 with the final partial batch retained; canonical ordering
followed by seeded epoch permutations; CPU/CUDA float32; AdamW at learning rate
0.001 with the declared defaults and candidate weight decay; no scheduler or
gradient clipping; and unweighted target BCE. Seeds derive from base `31032`
and exclude host identity.

## D032-04 - Neutral architecture selector

The later architecture screen uses only `target_only_resmlp` at
`fraction100/full`. This is the neutral selector: choosing architecture on the
multi-head innovation would favour the method under test. The selected shared
architecture will later be frozen across target-only, transfer, scalar-control,
species, and fraction paths.

Goal032 does not run that selector. It validates auxiliary eligibility only:
the focal target is absent; pseudoabsences and unknowns are absent; all seven
auxiliary species remain; each species contributes `1/7`; and aggregate
provenance/class counts reconcile with the frozen foundation.

## D032-05 - Exact calibration cases and arithmetic

All cases use base seed `31032`, a case-specific SHA-256-derived target seed,
and `fraction100/full`:

| Case | Architecture | Target | Held | Stop | Discovery |
|---|---|---|---|---|---|
| light | `resmlp00` | `pseudocheirus_peregrinus` | `fold03` | `fold04` | `fold00/01/02` |
| medium | `resmlp12` | `notamacropus_rufogriseus` | `fold03` | `fold04` | `fold00/01/02` |
| heavy | `resmlp23` | `sarcophilus_harrisii` | `fold01` | `fold02` | `fold00/03/04` |

Each case runs twice on Mac CPU, deep-server CPU, and Alien `cuda:0`: 18
logical evaluations and 36 physical discovery/replay fits. The leading serial
host then runs six queued tasks, two repeats of each case, for 12 more physical
fits. Total Goal032 execution is 24 logical evaluations and 48 physical fits.

The later 960-evaluation screen plus 480-evaluation shortlist therefore means
1,440 logical evaluations but **2,880 physical neural fits**.

## D032-06 - Resource choice and reproducibility

Serial comparison records wall time, selected epoch, peak RSS/VRAM, runtime
fingerprint, bundle digest, and model/prediction digests. Same-host semantic,
model, and prediction digests must repeat. Cross-host equality is not required:
one selected host/backend will run the complete Goal033 workload.

Rank passing hosts by projected concurrency throughput subject to deterministic
repeats, memory headroom, and no swap growth. Prefer CPU if the best CPU
throughput is at least 80% of GPU throughput. Alien uses at most one independent
worker per GPU and no DDP. Run the six-task panel only on the serial leader;
its observed throughput or instability may change the final recommendation.

Canaries run in isolated Python 3.12 environments with NumPy 2.2.6 and
PyTorch 2.7.1 on every host. Mac and deep-server use official CPU wheels.
Alien uses the official cu118 wheel, compatible with its NVIDIA driver 546.01.
The repository's current Linux lock resolves a different Torch/CUDA stack and
is not assumed compatible with Alien. Goal032 neither edits `pyproject.toml` or
`uv.lock` nor promotes this temporary calibration runtime to production.
Goal033 must separately freeze the selected host's production runtime.

## D032-07 - Evidence and review

Remote bundles contain transformed discovery/stopping/replay arrays and
label-free `x_held` predictors from the inner held fold only. That inner fold
is part of outer-training; it is never the sealed outer assessment. Bundles
contain no raw data, identifiers, coordinates, outer assessment, or held
response. Tracked evidence contains aggregates and digests,
never values, labels, losses, predictions, ecological metrics, or private
paths.

Implementation workers do not commit or push. Once every acceptance gate has
passed and the orchestrator accepts Goal032, the orchestrator may commit and
push under Barry's standing publication authority.

This is the central real-data implementation boundary. A bounded Sol Max audit
of membership, stopping leakage, neutral architecture selection, workload
accounting, and privacy is justified before Goal033 is launched.
