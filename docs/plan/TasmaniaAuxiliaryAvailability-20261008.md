# Tasmania auxiliary-state availability — 8 October 2026

**The historical Mac runtime remains installed, but the 200 accepted fold-specific multi-head states were not retained as weights.** Goal035 preserved their state digests, selected epochs, initialization/shared-state digests, replay-prediction digests and original input bundles. Exact reconstruction is supported by the source and metadata, but has not been attempted. This audit performed zero fits, scoring, held-response-array reads or remote connections.

The aggregate [audit](../../evidence/tasmania_pseudoabsence/20261008/auxiliary-state-audit.json) binds source/configuration digests, exact function lines, all 56 conventional selections and inspection limits. Receipt digest: `765e45c7f567c1e021d5954ea69b7d6d0bd11c3863efff2c855e7780cd562347`.

## Artifacts and runtime

The 40 accepted Goal035 leaves each contain only `metadata.json` and `predictions.npy`. There are 200 multi-head digest records, 200 pooled-model digest records and 40 q-model digest records. The 40 original bundles declare hashes for auxiliary replay covariates, responses and species indices; their metadata bundle identities match the leaves. Only the `metadata_json` member was read for this audit, so numerical-array validity remains unverified.

No saved model-state files exist in the canonical Goal035 private tree. A scoped filename search under `data/processed/dsdm` found auxiliary weight files only in Goal037 and its archival copies, including canary repetitions. External backups were not searched. Goal037 retains 40 accepted outer-training multi-head states in eight production packages; every model-file hash matches its receipt, and archived copies match and are hard links. These full outer-training states cannot substitute for inner states that excluded a held fold.

The neural executable is:

`/Users/bwbrook/papers/dSDM/data/processed/dsdm/goal034-real-six-path-sentinel/runtime/.venv/bin/python`

It resolves to CPython 3.12.13 on Darwin arm64. Installed metadata matches NumPy 2.2.6, SciPy 1.16.3, scikit-learn 1.9.0, threadpoolctl 3.6.0, Torch 2.7.1 and pyarrow 21.0.0. Numerical/thread attestation and fitting smoke remain unrun. Retain the three-worker, one-thread-per-worker Mac route. All 16 Goal035 and 12 Goal037 executable-source bindings checked in `data/processed/dsdm/tasmania-outer-assessment-20261005/archive/goal037-ce70bf1` match; import from that archive. The live Goal028 parameter configuration also matches its accepted hash. However, nine of the ten Goal035 authority files are absent from the existing outer-prediction archive. All ten have matching accepted hashes in the live repository. The archived `load_config` requires those files, so that archive is not directly runnable as a Goal035 config root. Stage a separate reconstruction root with these hash-verified original authorities, or explicitly bind the two roots; preserve the accepted archive and its strict checks.

Conventional fitting requires the historical Linux/x86-64 Goal029 producer on `deep-server`: commit `f85e45922e182858fd351fdaf4f1b36b33fb4f2f`, validator `e6f07ae8bdb48399af907cf44598cc34d51391f6`, Python 3.12.3, NumPy 2.5.1, SciPy 1.16.3, sklearn 1.9.0, Torch 2.13.0 and pygam 0.10.1, using four single-threaded workers. The inspected runbooks identify the producer by commit and historical alias `deep-server-ts`, without a usable absolute checkout path. Locate and attest it before execution. Local availability of 952 selected conventional models supports prediction replay; the current Darwin scorer environment does not prove Linux fitting parity.

## Minimal amendment proposed

The proposal states: “Accepted fold-specific auxiliary states and `q` must be reused byte-for-byte; no auxiliary refit or new `q` estimate is permitted.”

Archived `final_inner_runner._case_lifecycle` constructs auxiliary models in memory and returns predictions plus metadata. `final_inner_data.write_leaf` writes only those two products. Retained state digests are therefore available, but loadable fold-specific models are not.

Permit **200 replay-only multi-head reconstructions**, one per species × inner fold × accepted seed, on the unchanged original auxiliary replay arrays and mask. Use the original species ordering, seed, architecture, historical source/runtime and recorded replay epoch count. Do not repeat discovery, choose epochs or modify auxiliary memberships. Archived `real_six_path._neural_lifecycle` lines 379–411 reset the seed/factory and call `_train_epochs`; `outer_ready.exact_fit` uses the same machinery. Every one of the 200 metadata records has the needed epochs and digest fields.

Before any sensitivity target fit, require every reconstruction to reproduce exactly the accepted initialization, initial and final shared state, complete model state and auxiliary replay prediction digests, after checking input, mask, source and runtime digests. Any mismatch fails reconstruction without relaxed tolerances, new discovery or runtime substitution. Save recovered weights privately with fresh serialization hashes bound to the original semantic state digests. Since no original serialized weight file exists, byte equality refers to the tensor-state bytes covered by the accepted state digest.

The three selected paths do not consume `q` or pooled-pretraining models. Target-only uses fresh initialization, full multi-head fine-tuning copies the multi-head shared state, and conventional fitting uses its own adapter. Clarify the contract to permit **zero pooled and zero q reconstructions/refits**, retaining their existing provenance only. Reuse the 40 accepted outer multi-head states directly. This audit does not authorize reconstruction or establish that it will pass.

## Replay and filtering semantics

Use archived `_neural_lifecycle` for both target paths. `resmlp13` has three constant blocks, width 128, bottleneck 64, dropout 0 and weight decay 0.001; AdamW learning rate 0.001, batch size 128, float32 CPU, maximum 300 epochs, patience 30 and strict stopping-loss improvement. Both target paths use the same Goal035 target-seed derivation, retaining matched initial heads. Stopping fold is `(held + 1) mod 5`; replay resets the same seed/factory on retained complete CV-training rows for the selected epoch. Outer target fits retain Goal037 seed derivation and the lower median of five new sensitivity selected epochs.

Fit the target categorical support mask from retained complete replay rows with `categorical_support.fit_support_mask`, and apply it to all fitting and prediction roles. Conventional `FeatureProvider.fit_encoder` likewise uses retained complete endpoint rows; reuse its encoder across discovery/stopping/replay while retaining the Goal026 map-derived transforms. Generic archived `run_candidate_oof` and `refit_outer_training` reject changed canonical endpoints. Sensitivity orchestration must implement exact subtraction explicitly and call the lower-level adapter, without weakening historical endpoint checks.

The conventional API is `build_adapter(family).fit(train_batch, stopping_batch_or_none, candidate, derived_seed, exact_epochs=...)`. ANN discovery is followed by same-initial-state replay at `best_epoch`; outer ANN uses the lower median of five new inner epochs. Other selected families use one fit per fold. Preserve canonical `TaskKey`/`derive_seed(task, "fit")` and family seed policies. Average seed probabilities before deriving sensitivity-specific pooled-OOF maximum-TSS thresholds with the accepted lower-median tie rule.

## Frozen 56-stratum inventory

Source: `evidence/dsdm_inner_evaluation/goal036/conventional_selection.csv`, SHA-256 `3e05784670f58e88144dcbda43819c3811e8303c59cd15c36f23fdf38736a561`. The JSON audit includes every candidate's exact parameters and seed labels. Column order is the seven canonical endpoints; prefixes identify RF, HGB, ANN and elastic net.

| Species | 25/00 | 25/01 | 25/02 | 50/00 | 50/01 | 50/02 | 100/full |
|---|---|---|---|---|---|---|---|
| thylogale_billardierii | rf05 | rf06 | rf06 | hgb04 | hgb01 | hgb00 | hgb00 |
| notamacropus_rufogriseus | ann03 | ann04 | ann04 | ann05 | ann04 | hgb00 | hgb00 |
| trichosurus_vulpecula | rf00 | rf00 | rf00 | rf00 | rf00 | rf01 | rf00 |
| pseudocheirus_peregrinus | ann04 | enet00 | ann01 | ann03 | ann04 | ann03 | ann04 |
| vombatus_ursinus | ann05 | ann00 | ann04 | ann04 | ann05 | ann03 | ann04 |
| sarcophilus_harrisii | rf00 | rf00 | rf01 | rf00 | rf00 | rf00 | rf01 |
| dasyurus_maculatus | rf06 | ann04 | ann05 | rf04 | ann05 | rf02 | rf02 |
| dasyurus_viverrinus | rf05 | hgb05 | rf00 | hgb06 | hgb06 | hgb06 | rf00 |

| Component | Strata | Inner fits | Outer fits | Total |
|---|---:|---:|---:|---:|
| Two neural paths, five seeds | 56 × 2 | 5,600 | 560 | 6,160 |
| Random forest, five seeds | 24 | 600 | 120 | 720 |
| HGB, one seed | 10 | 50 | 10 | 60 |
| ANN, five seeds, discovery + replay | 21 | 1,050 | 105 | 1,155 |
| Elastic net, five seeds | 1 | 25 | 5 | 30 |
| **Target production total** | | **7,325** | **800** | **8,125** |

The prescribed 14 non-promotable smoke fits bring target execution to 8,139. If the minimal amendment is approved, 200 auxiliary replay fits bring total physical execution to **8,339**, without changing the 8,125 target-production count. Resource caps still require the fixed smoke receipts.
