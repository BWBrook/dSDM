# Decision

## Scientific question and estimands

Goal 039 is an inner-only sensitivity experiment: does a prespecified,
response-blind reduction of the 28-raw-predictor substrate improve relative
habitat-suitability transfer? The frozen architecture is `resmlp13`; no
architecture or hyperparameter tuning is permitted.

The only dSDM arms are `target_only_resmlp` and
`multihead_full_finetune`. In the definitions below, `TO` and `MH` refer to
those exact identifiers. The primary lanes are:

- `Delta U`: reduced-substrate minus full-substrate
  `multihead_full_finetune` performance.
- `Delta I`: the difference-in-differences between reduced and full
  `multihead_full_finetune` versus `target_only_resmlp` lift.

AUC and TSS are primary summaries. Species are equally weighted. MCC and
other endpoint/fold detail are descriptive. The intercept-only baseline remains
invariant.

For each species, endpoint, method and substrate, common-seed predictions are
averaged before fold metrics. Folds are then equally averaged within species,
and species are equally averaged. Thresholds are selected separately for each
substrate and method from its concatenated five-fold common-seed OOF scores by
the frozen Goal036 pooled-OOF maximum-TSS rule. Endpoint, species and seed
positivity gates refer to AUC; TSS is the aggregate directional guard. A
seed-level value is the equal-species mean of that seed's equal-fold effects
across the lane's declared endpoints.
An endpoint value is the equal-species mean of species' equal-fold AUC
effects. A species value is the equal-endpoint mean of that species'
equal-fold AUC effects. Aggregate TSS is the equal-species mean of species'
equal-endpoint mean TSS effects.

## Predictor masks

Exactly five deterministic masks are constructed, one per held spatial fold.
Each uses only the unique complete outer-training `D_struct` map cells for
that fold. Held-fold cells, outer data, occurrence responses, labels,
predictions, model results, and response-derived importance are excluded.

The 77-column shape is preserved. Excluded BIOCLIM columns are neutralised to
zero after the held-fold-specific Goal026 standardisation. The five BIOCLIM
blocks are reduced independently by complete linkage on absolute Spearman
correlation at `0.85`:

1. `BIO1`, `BIO8`--`BIO11`
2. `BIO5`--`BIO7`
3. `BIO2`--`BIO4`
4. `BIO12`--`BIO14`, `BIO16`--`BIO19`
5. `BIO15`

Complete linkage creates one or more clusters within each block; retain one
medoid per resulting cluster. The medoid maximises mean absolute within-cluster
Spearman correlation, with singleton clusters retaining their only member and
exact ties resolved by the explicit Goal026 feature order. Always retain
`elevation`, `top_roughness`, `dist_fw`, `dist_road`, `fpar`,
`human_footprint`, `soil_class`, `veg_mvg`, and `landuse_secondary`. The
existing categorical support policy is unchanged. Every mask must be finite,
represent every block, retain every mandatory predictor, and remove at least
one BIOCLIM predictor. Report all ten pairwise Jaccard similarities among the
five primary masks. Also derive masks at correlation thresholds `0.80` and
`0.90` as response-blind selector diagnostics only; no Jaccard value or
alternate threshold is an advancement gate.

## Model context and workload

The reduced mask is applied identically to dSDM and to the frozen
Goal029-selected-within-family candidates for elastic net, random forest,
histogram gradient boosting, and shallow ANN. Conventional context is
descriptive and cannot trigger reduced-panel adoption. For each species,
endpoint and family, the reduced fit reuses the exact Goal029 selected
candidate, hyperparameters, response rows, folds, and canonical family seed
labels. Its `full28` comparator is fitted contemporaneously under the same
locked runtime, rows, folds, and seeds, so reduced-minus-full effects are
paired within the current numerical environment. The immutable Goal036 OOF
export remains authoritative for candidate selection, row and label identity,
and historical provenance; historical score differences are canary
diagnostics, not equality gates or effect baselines. Neural seeds
31031--31035 apply only to dSDM.

This amendment was frozen before the screen after a bounded canary diagnosis
found exact row, label, candidate, and seed agreement for all four families,
but a maximum historical-refit difference of `0.00556825` for random forest
across Linux/x86 and Darwin/arm64. Elastic net, histogram gradient boosting,
and shallow ANN differed by at most `1.49e-7`. The random-forest tolerance is
not widened post hoc. Instead, the conventional canary records the historical
drift by family and requires exact current-runtime repeatability, finite
predictions, and probability bounds for both full and reduced fits.

The neural canary replays the full-28 sentinel once against its immutable
predictions and fits the reduced sentinel twice. The conventional canary fits
both full and reduced sentinels twice in the locked current runtime, validates
the immutable Goal036 lineage and row/label identities, and reports historical
score drift without using it as a gate. The screen uses
`fraction25/ladder00`, `fraction50/ladder00`, and
`fraction100/full`, with seeds `31031`--`31033`. A lane advances only when it
is positive in at least 2/3 endpoints, at least 5/8 species, at least 2/3
seeds, and aggregate TSS is non-negative. Lanes advance independently; a lane
that fails this screen is ineligible for confirmation and cannot be revived.

If either primary lane advances, confirmation uses
`fraction25/ladder01`, `fraction25/ladder02`, `fraction50/ladder01`,
`fraction50/ladder02`, and `fraction100/full`, with reserved seeds `31034` and
`31035`. Confirmation requires positivity in at least 4/5 endpoints, at least
5/8 species, both reserved seeds, and aggregate TSS non-negative. A `Delta I`
claim additionally requires aggregate `Delta U` AUC and TSS to be
non-negative.

Reserved seeds are internal robustness checks, not pristine independent
confirmation. Nested endpoints and folds are not independent confirmation
units. No alternate rescue is allowed.

The final decision table is frozen:

- confirmed `Delta U` permits a later reduced-panel outer-ready proposal,
  without asserting a transfer mechanism;
- confirmed `Delta I` supports enhanced transfer only when aggregate `Delta U`
  AUC and TSS are both non-negative;
- confirmed `Delta I` without that guard is rejected as relative lift caused
  by target-only degradation; and
- no confirmed eligible lane retains `full28`.

## Boundaries

Do not open the outer vault, generate maps, process birds, revise the
manuscript, tune architecture or hyperparameters, or rescue with VIF/PCA or
another response-aware reduction. No predictor mask may be selected from
responses or downstream performance. The Goal024 domain, 2001--2025 response,
pseudoabsence, temporal, and spatial-fold contracts remain unchanged.
