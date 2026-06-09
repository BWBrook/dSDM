# dSDM 30,000-foot strategic plan

Date: 2026-05-27

## Strategic commitment

The dSDM repo will be rebuilt Python-first.

The existing R code, processed CSVs, notes, and manuscript draft are important
archaeological artifacts. They preserve intent, assumptions, partial methods,
and useful warnings. They are not canonical implementation targets and should
not be treated as an unblemished workflow to mimic.

The core scientific and software posture is:

1. Rebuild from primary data wherever practical.
2. Treat old processed outputs as comparison/reference artifacts, not truth.
3. Develop the Tasmanian mammals case study first.
4. Use the SE Australia birds case study only after the Tas workflow is proven.
5. Keep the manuscript, code, data provenance, and results generation coupled.
6. Maintain a live plan, revising it at each gate as evidence accumulates.

## Case-study sequencing

### First: Tasmanian mammals

The Tasmanian mammals case study is the proving ground because it is bounded,
ecologically meaningful, and computationally tractable:

- smaller spatial extent;
- 9 focal species;
- known mixture of camera-trap true absences and ALA-derived records;
- real prevalence imbalance that reflects ecology rather than a toy example.

All data acquisition, cleaning, formatting, modelling, metric, mapping, and
manuscript-output decisions should be proven here first.

### Later: SE Australia birds

The SE Australia birds case study is the scale-out validation, not the smoke
test surface:

- much larger spatial extent;
- 100 species;
- substantially larger processed datasets;
- suitable for demonstrating generality once the Tas workflow is robust.

No major modelling architecture or data-processing logic should be debugged for
the first time on the SE birds workload.

## Phased strategy

### Phase 0: Preserve, inventory, and orient

Create a durable project map before rebuilding.

Phase 0 should inventory:

- tracked repo scaffold and current broken/missing pieces;
- ignored payloads under `temp/` and `data/`;
- legacy R scripts and the workflow intent they imply;
- existing processed CSVs and spatial files;
- manuscript draft and publication needs;
- missing artifacts, unclear provenance, and known defects.

Phase 0 should produce enough clarity to decide what Phase 1 must acquire,
rebuild, and verify. It should not implement the new data-acquisition workflow.

### Phase 1: Re-acquire and rebuild primary data

Rebuild the upstream data pathway in modern Python rather than converting the
old processed CSVs into a new format as the foundation.

This phase should cover, in detail only after Phase 0 has passed:

- focal species metadata;
- ALA acquisition;
- camera-trap data ingestion;
- spatial boundary and grid handling;
- coordinate cleaning and snapping;
- pseudoabsence logic;
- true-absence versus pseudoabsence provenance;
- offshore-island exclusions;
- thinning and sampling-bias controls;
- spatial train/test/fold construction;
- predictor extraction;
- scaling and encoding;
- reproducible data manifests.

The old CSVs remain useful for comparison, but regenerated data will be the
scientific basis for downstream modelling.

### Phase 2: Data QA and acceptance

Before modelling, regenerated Tas data must pass explicit QA gates.

Checks should include:

- row counts by species, source, presence/absence, and split;
- spatial extent and boundary membership;
- duplicate grid-cell handling;
- missingness;
- prevalence and imbalance summaries;
- fold balance and spatial separation;
- predictor schemas and ranges;
- reproducibility under fixed seeds;
- documented deltas from legacy artifacts.

Only accepted data products become the modelling substrate.

### Phase 3: Tasmanian mammals modelling substrate

Freeze the first accepted Tas modelling dataset and build clean modelling
infrastructure around it.

This includes:

- repo-local Python package structure;
- `uv`-managed environment;
- canonical configs;
- data schemas/manifests;
- tested metrics and thresholding;
- baseline models;
- reproducible run manifests.

### Phase 4: Tasmanian mammals dSDM modelling

Rebuild the deep-learning work in native Python Keras 3.

Core modelling should cover:

- no-transfer dSDM;
- paired-species transfer;
- sequential transfer;
- community/melting-pot transfer;
- spatial jitter augmentation where scientifically justified;
- Alien GPU execution for Keras workloads that fit dual RTX 2080 GPUs.

The legacy R-Keras code should be mined for design intent, not copied.

### Phase 5: Manuscript integration

The manuscript should become a consumer of the rebuilt workflow.

Outputs from the accepted modelling pipeline should drive:

- metric tables;
- maps;
- ROC/PR curves;
- figure captions;
- Methods text;
- Results and Discussion claims.

The current converted draft is a scaffold. It should be revised in step with
the code and data evidence.

### Phase 6: SE Australia birds scale-out

After the Tas workflow is locked down, apply the same pipeline to the SE birds
case study.

This phase should test:

- whether the data-acquisition workflow generalises;
- whether compute routing is adequate;
- whether the dSDM conclusions hold at larger spatial and taxonomic scale;
- which results belong in the main paper versus supplementary material.

## Gate discipline

Detailed planning is gate-based.

Only Phase 0 should be planned in implementation detail next. Phase 1 should not
be specified in detail until Phase 0 has produced a clear inventory, risk map,
and acceptance criteria for moving forward.

At each gate, the live plan should be revised from evidence:

1. What did we learn?
2. What broke or proved stale?
3. What assumptions should be retired?
4. What artifacts are now canonical?
5. What must be true before the next phase starts?

## Current next step

Write, implement, test, and revise a detailed Phase 0 plan.

Phase 0 completion should be an explicit project gate. Passing it should produce
the basis for writing the detailed Phase 1 primary-data acquisition plan.
