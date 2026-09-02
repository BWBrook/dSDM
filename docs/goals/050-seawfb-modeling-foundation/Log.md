# Goal 050 log

## 2026-09-02

- Implemented the model-free foundation builder and fail-closed CLI.
- Recomputed the full 0--511 spatial seed search with the frozen Goal 043 hash
  assignment; selected seed `394` under
  the frozen tie-break.
- Built 787,357 retained-training cells, 784,967 complete-predictor cells,
  and 1,630,551 sparse memberships for 183 heads.
- Wrote privacy-safe tracked receipts and passed private and tracked validation.
- No models, predictions, performance outcomes, raw occurrence rows, or outer
  region outcomes were opened.
- This foundation log records no production/scientific fit, prediction
  product, loss/score, threshold, or ecological outcome.

## 2026-09-02 foundation audit repair

- Rebuilt the response-row plan for all 157 focal targets across all five held
  folds: 365 primary nested 25/50/100 endpoints and 420 full-only endpoints
  for the remaining focal targets.
- Clarified that held-block-adjusted richness is used only for auxiliary
  pretraining backgrounds; target-specific fine-tuning/evaluation uses full
  richness with target-specific X10.
- Bound the generator source, locked Python environment, and authoritative
  IBRA geometry in the manifest. Stale `run.exit` markers are removed at build
  start and completion markers are checked against the current manifest.

## 2026-09-02 compute-canary gate

- Added the bounded canary runner, deterministic bundle format, focused tests,
  and privacy-safe canary receipts.
- Initial export halted as required: strict non-held-fold candidate rows =
  `94,873`, below the initial `100,000` (`54,828` adjusted-richness rows and
  `94,815` complement-head presence rows in the union).
- Authorized resolution changed only the canary bundle size to `90,000`.
  Exact frozen eligibility is unchanged; no scientific eligibility rule was
  relaxed.

## 2026-09-02 compute-canary execution

- Re-exported the final deterministic bundle `bundle-6a1ead837ee61b10f29d4039278f9e34b7441bea4fc17bc6b1ad5bf99c18d280.npz` with `90,000` rows, `167` heads, encoded width `103`, and metadata digest `708bdd7e74a56e84ffc58003aa09eb2a15f2dcb5986f2867b90aee0fc1b3c8af`.
- Ran two clean processes each on Mac CPU, deep-server CPU (`deep-server-ts`),
  and Alien `cuda:0` (`alien-wsl`). All six runs were finite, deterministic,
  memory-safe, and recorded zero ecological metrics. Within each host, state
  and fixed-probe digests matched exactly.
- Median multi-head fit-only times were `1.579` s (Mac CPU), `10.824` s
  (deep-server CPU), and `19.995` s (Alien GPU). Mac won single-job latency.
- Aggregate calibration passed at Mac concurrency 3 (`4.206` s batch,
  `21.44M` row-head-epochs/s), deep concurrency 16 (`31.409` s,
  `15.31M`/s), and deep concurrency 32 (`35.688` s, `26.95M`/s), all with
  requested jobs successful. Deep therefore won aggregate CPU capacity by
  `1.26x` over Mac and was selected for bridge-like vectorized PyTorch grids.
  Goal051 conventional models require their own small family-representative
  resource gate. No production job was launched.
- Mac and deep CPU used fresh `uv sync --locked` environments with NumPy
  2.5.1 and Torch 2.13.0; Python patch versions were 3.12.13 and 3.12.3,
  respectively. Deep's Torch build is tagged `+cu130` but was forced to CPU.
  Alien retained the compatible Torch 2.7.1+cu118 environment (CUDA 11.8,
  driver 546.01), explicitly hardware-compatibility evidence rather than a
  lock-matched production runtime.
- Alien's first attempt stopped at PyTorch's CuBLAS determinism precondition;
  the two final Alien repeats were rerun with
  `CUBLAS_WORKSPACE_CONFIG=:4096:8` and both passed, recording driver `546.01`.
