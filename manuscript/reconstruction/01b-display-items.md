# Step 1b: Display items

**Status:** locked draft v2, 12 November 2026 (converged with Codex, thread 162, message 3337). Barry approved v1 in chat. v2 applies Codex's review (`docs/audits/reconstruction-review-20261112.md`, R4, R8, R9, R11 and R13). It is to be checked on Barry's full read.

Main message (step 1a): *Training AI on many species improved predictions in familiar regions, but on average not in new ones, where predictions matter most.*

## Budget

**Four figures and one table: five of Ecography's six.** The main text runs to about 4,650 words against the 5,000 limit, so every display item has to carry a point the text cannot. The sixth slot stays free, and everything else goes into a single Supporting information file.

## Principles for every item

- **One point per item.** The title is a sentence stating that point. The caption explains how to read the figure and defines what is plotted. Limitations belong in the Discussion's limitations paragraph.
- **Plain labels.** Use "familiar regions" or "development region" and "new regions"; avoid "inner/outer CV", "OOF" and "region × fold". Name the learners "pretrained network", "single-species network" and "conventional model".
- **One colour per learner, the same in every figure.** For example: pretrained network blue, single-species network orange, conventional model grey, ensembles green.
- **Show species, not only means.**
  - Bird panels: species points, the mean, and the paired central 95% species-composition resampling range. The caption defines it as conditional on the observed panel and fitted models. Do not call it a confidence interval.
  - Mammal panels (5 and 8 species): points and means only.
- **Share scales wherever the comparison matters.**
- **Maps show public boundaries only.** No camera sites, no masks derived from cameras, and no Tasmanian held-out patches drawn as real locations.

## Proposed items

### Figure 1: Study design (new context item)

*Three tests of whether learning from other species helps in new regions.*

- **(a) Map.** Start from the boundary-only `evidence/seawfb_bioregional_freeze/goal048/selected_holdouts.svg` and redraw it at print resolution. Show:
  - the bird development domain;
  - the three withheld bioregions (NCP, SEH, NNC) with their 50 km buffers;
  - the mainland mammal source region, with Tasmania as its transfer target.
  An explicitly schematic Tasmanian inset shows the held-out-patch design.
- **(b) Schematic of three learners and two comparisons.**
  - Learners: a pretrained network (learns from other species, then the target); a single-species network (same architecture, target only); a conventional model selected within the development data.
  - **Pretrained minus single-species** is what learning from other species adds.
  - **Single-species minus conventional** is what the network adds by itself.
  - Rules shown: the target species is excluded from pretraining, and the withheld regions are excluded from all fitting.
  - The frozen-encoder and scalar community controls appear as a labelled branch pointing to Supporting information.

### Figure 2: The main result (rebuilt from current Fig. 1 and Fig. 2b)

*Learning from other species helped in familiar regions but not, on average, in new ones.*

- **(a) Birds: pretrained minus single-species network, paired species points, one scale.**
  1. Development, whole domain: +0.0058, 72/73 species positive.
  2. Development scored **within bioregions and spatial folds**: +0.0072, 68/73.
  3. New regions: −0.0004, 34/73. Mark the regional means: NCP +0.0064, SEH −0.0040, NNC −0.0035.
  Link the species across settings, so the reader sees the average gain disappear while individual species still vary.
- **(b) Mammals, same contrast, large points:**
  - mainland development +0.0087 (4/5), then transfer to Tasmania −0.0155 (3/5);
  - Tasmania development −0.0068, then held-out patches −0.0147.

### Figure 3: What helps in new regions (rebuilt from current Fig. 2b and its callout)

*In new bird regions the network's advantage was available without pretraining, and averaging with a conventional model gained most.*

New bird regions only. Each row is a difference from the conventional model, shown as species points, a mean and a resampling range:
1. single-species network: +0.0032;
2. pretrained network: +0.0028;
3. fixed 50:50 single-species/conventional ensemble: +0.0096 (post hoc);
4. fixed 50:50 pretrained/conventional ensemble: +0.0104 (prespecified as exploratory).

The provenance of rows 3 and 4 is stated once, in the Methods. Region-by-region results go to Supporting information.

### Figure 4: Negative evidence changes the ranking (merges current Fig. 3 and Table 2)

*Model rankings changed with how well recorded the negative observations were.*

- **(a) Birds.** Pretrained network minus conventional model, plotted against background recording richness (10–24, 25–99 and ≥100 other species recorded).
  - Development: 59 species.
  - SEH: 38 species; NNC: 55 species.
  - NCP has no common three-bin estimate; say so in the caption.
- **(b) Tasmania.** A 2×2 of training (original vs pseudoabsences removed) by evaluation (mixed negatives vs survey-supported negatives only), plotting AUC for each learner as dots joined by lines. The TSS half of the current Table 2 moves to Supporting information.

### Table 1: Cases and absolute performance (merges current Table 1 with Table S1f)

- Rows: each case and setting, with the three bird regions and the pooled bird result as subrows.
- Descriptor columns: species count, prediction task, and what was excluded from fitting.
- Performance columns: AUC for the three learners, in development and in new regions.
- Ensembles stay in Fig. 3, and there are no mammal ensemble cells.

## Moved to Supporting information

- Learning curves: target data and auxiliary pool, including the frozen-encoder trajectory.
- TSS for all cases, including the Tasmanian disagreement between AUC and TSS. The main text keeps one sentence on it.
- Absolute AUC under each scoring extent, as a full panel.
- Per-region and per-species breakdowns.
- Maps of how pseudoabsence removal changes predictions.
- The scalar community controls.

## Production notes

- **No new fits are needed.** Mammal neural/conventional ensembles are left out. Building them would need aligned prediction vectors and labels, and the saved outer vectors for the mainland transfer are not established.
- **Bird resampling ranges.** Existing ranges cover development and new-region pretrained minus single-species, and pretrained minus conventional. Ranges for the within-bioregion-and-fold rescoring and for the ensemble rows are a bounded reporting extension (Codex). They use retained species aggregates in `evidence/seawfb_dsdm/goal052/extent-review-20261005.json`, with no fitting and no access to raw responses.
- **Map geometry.** Display geometry uses 3 km simplification; the analysis geometry is unchanged. Make no claim of a "safe" grid resolution.
