# Step 1a: Working abstract (Key Questions)

**Status:** locked draft v3, 13 November 2026. Revised against Codex's review (`docs/audits/reconstruction-review-20261112.md`, thread 162, message 3329) and convergence check (`docs/audits/reconstruction-convergence-20261112.md`, message 3337). It is still to be checked on Barry's full read. It is a working reference and will not be submitted. The target journal is Ecography.

## Main message (21 words)

> **Training AI on many species improved predictions in familiar regions, but on average not in new ones, where predictions matter most.**

"Familiar regions" means unseen locations inside the region where the model was developed. "New regions" means areas kept out of all model development. The paper names the positive cases explicitly: mainland mammals and birds.

Earlier versions:
- Barry-approved v2 (24 words): "Training AI on many species helped it predict where one species lives, but only in familiar places, not new ones, where predictions matter most." Codex's review R1 found that "only" overstates the result. One bird region (NCP) and some individual species did benefit in new places, so the claim is now about the average.
- v1 (22 words): too technical for a general reader.

## Why are we doing this?

Neural networks that learn from many species promise better distribution models, and their gains weaken under transfer. A successful multi-species model does not reveal what sharing contributed; that requires the same network trained only on the target, tested in regions excluded from development.

## Aims and research questions

**Core question:** Does learning from other species improve a target's distribution model in new regions?

**Sub-questions:**
- How does the gain change as the target's own records shrink?
- Do model rankings depend on the evidence used for absence?

## Predictions and diagnostic question

The first three predictions follow from shared responses to environment and were built into the original design.

1. **Development gain.** Pretraining on other species improves prediction within the development region.
2. **Borrowing strength.** That gain grows as the target's own records shrink.
3. **Transfer.** The gain persists in new regions. If it fails, the result alone does not tell us why: the shared information may be niche structure, recording patterns, or an optimisation effect.

The fourth item is a diagnostic question, not a prediction. It arose from the development results and was fixed before the new-region data were opened. The Tasmanian survey-only check came later.

4. **Negative evidence.** Do model rankings change with how well recorded the negative observations are?

## What we did

- Multilayer perceptrons were pretrained on other species and fine-tuned to each target.
- Each was compared with an identical network trained on the target species only, and with a conventional model selected within the development data.
- Three cases:
  - Tasmanian mammals, scored on held-out patches;
  - mainland mammals transferred to Tasmania;
  - 73 birds scored on three withheld bioregions.

## What we found

- **Development:** pretraining raised AUC for mainland mammals (+0.009) and birds (+0.006). The bird gain grew to +0.009 at a quarter of the target data.
- **New regions:** no average gain (birds −0.0004; mammals −0.016).
- **Bird networks** beat conventional models with or without pretraining (+0.003).
- **Ensembles** gained the most (+0.010).

## What the results mean

The development benefit of learning from other species did not carry into new regions on average. The network's advantage there was available without pretraining. Model rankings depended on which negative observations scored them.

## What it is good for, and how it generalises

Claims that a multi-species model's success comes from learning across species need a matched single-species twin. That twin must be tested in the regions, and against the observations, where predictions will be used. This holds for any taxon or region.

## Notes for later steps

**Novelty.** Basile et al. (2026, Ecography, 10.1002/ecog.08269) already show that neural joint models weaken under regional transfer. Our contribution is the **attribution**: target-excluded pretraining, a same-architecture single-species control, and geographic exclusion. The extent and negative-evidence diagnostics support it.

**Provenance**, to be stated once in Methods:

| Element | Status |
|---|---|
| Matched comparisons and target-data curves | Original design |
| Richness gradient | Found in development; outer version fixed before opening |
| Extent rescoring, single-species ensemble and survey-only negatives | Post hoc |
| Fine-tuned ensemble | Prespecified as exploratory |

**Wording.**
- The extent diagnostic scores development predictions **within bioregions and spatial folds**. It does not match areas.
- In Tasmania, the "survey-supported negatives" are nondetections, not confirmed absences.

**Correction (Claude, 12 November).** The recording-richness gradient concerns background *places*, not sparsely recorded species. The least-recorded third of species led conventional models by only +0.0006, but led the single-species network by +0.0041.

## Draft abstract v3 (149 words; target under 150 for now; Ecography limit 300)

Neural networks that learn from many species promise better distribution models, yet the source of their gains is rarely tested against an identical network trained on the target alone, in new regions where predictions are used. We pretrained multilayer perceptrons on other species, fine-tuned them to each target, and compared them with matched single-species networks and conventional models in Tasmanian mammals, mainland mammals transferred to Tasmania, and 73 birds in three withheld bioregions. Pretraining improved development discrimination for mainland mammals and birds (AUC +0.009 and +0.006), especially when bird records were subsampled, but gave no average gain in new regions (mammals −0.016; birds −0.0004). In new bird regions, the network's advantage over conventional models was available without pretraining (+0.003), and averaging network and conventional predictions gained most (+0.010). Model rankings changed with the source of negative observations. Multi-species gains should be measured against single-species twins where predictions are needed.
