# Step 1: Working abstract (Key Questions)

This is a working reference for reconstructing the paper; it will not be submitted. The draft it was written against is at `9e2b227`, and the target journal is Ecography.

## Main message (22 words)

> **Learning from other species improved neural distribution models within their training region, but not in new regions, where predictions are most needed.**

Every section should serve this sentence. The lines of evidence that support it, rather than compete with it:
- **The target-only twin.** The small neural advantage in new regions was available without pretraining.
- **Ensembles.** The practical gain comes from combining learners, not from sharing across species.
- **Extent and negatives.** Absolute scores and rankings depend on how the test is defined, so the comparison must be matched.

Superseded draft (24 words): "Multi-species pretraining slightly improves distribution models within the training region, but the advantage vanishes in new regions; ensembling neural with conventional models gains more." This carried two messages, the pretraining null and the ensemble gain. The ensemble result now serves as evidence for the main message instead.

**Terminology (Barry, 12 November 2026).** "Deep" was Barry's original term, and he is not wedded to it. Describe the model as a neural network: a multilayer perceptron, a standard deep-learning model. Avoid "deep SDM", because readers may take it to mean image or spatial models. This means revising the opening of the v1 abstract.

## Why are we doing this?

Deep and joint SDMs promise better predictions for each species by learning from many species. That promise has rarely been tested against a matched single-species network where SDMs are actually used: in new places.

## Aims and research questions

**Core question:** does learning from other species improve a target species' distribution model when it predicts into new regions?

**Sub-questions:**
- Does any gain come from pretraining itself, or from using a neural network at all?
- How do the evaluation extent and the definition of negative observations change the answer?

## Hypotheses (a priori, grounded in theory)

1. **Shared niche structure.** Species respond to common environmental gradients, so a representation pretrained on other species should improve target prediction within the training domain.
2. **Borrowing strength.** Pooled information should matter most when the target's own data are scarce, so the gain should grow as target records shrink.
3. **Transfer under domain shift.** If the shared representation captures general niche structure, the gain should persist in new regions. If it captures structure specific to the training domain, such as co-occurrence or recording patterns, the gain should shrink.
4. **Shared observation process.** Species share observers, so models learn where people record as well as habitat. The neural advantage should therefore depend on whether negatives come from poorly or well-recorded places.

## What we did

- We trained residual neural networks on many other species and fine-tuned each one on a target species.
- We compared these against identical networks trained only on the target, a frozen-encoder control, and tuned conventional SDMs.
- We used three Australian cases (Tasmanian mammals, mainland mammals transferred to Tasmania, and 157 birds) and held out whole bioregions.
- Primary models and scoring were fixed before we looked at outcomes.

## What we found

- Pretraining improved discrimination within the training region (+0.006 to +0.009 AUC), but that gain vanished in the held-out regions (birds −0.0004, mammals transferred to Tasmania −0.016).
- The network trained only on the target still beat conventional models there (+0.003).
- Neural–conventional ensembles gained most (+0.010).
- Rankings shifted with evaluation extent and with how negatives were defined.

## What the results mean

- The gains a successful pretrained model appears to make are mostly available without learning from other species.
- The shared representation encodes structure that does not transfer, consistent with hypothesis 3's second branch.
- Labels and recording processes, not the learner, set the ceiling on performance.

## What it is good for, and how it generalises

Any claim that transfer helps should be tested against a target-only twin, in the regions and with the observations where predictions will be used. Ensembling neural and conventional models is a cheap gain. Improving observation data is likely to beat adding model complexity. Both apply to any taxon or region.

## Notes for later steps

- The current draft states no hypotheses. Hypotheses 1–4 map onto evidence it already has:
  - **H1:** the gains within the training domain.
  - **H2:** the target-data learning curves, plus the least-recorded third of species (+0.0006 against conventional models, +0.0041 against the target-only network). H2 is only partly supported: the gain grew under subsampling, but the least-recorded species gained little against conventional models.
  - **H3:** the held-out region results, and the extent-matched analysis showing the pretraining gain stays positive within regions in the development data.
  - **H4:** the recording-richness gradient, which was a prospectively fixed diagnostic in the held-out regions, and the Tasmanian survey-only negatives, which were post hoc.
- **Correction to an earlier Claude answer in chat (12 November).** The recording-richness gradient refers to **places**: background cells with few other recorded species. It does not refer to sparsely recorded species. The neural advantage over conventional models was largest against poorly recorded background, and smallest or negative against well-recorded background. Among the least-recorded *species*, the advantage over conventional models was almost nil.

## Draft abstract v1 (149 words; target <150 for now, Ecography limit 300)

Deep species distribution models promise better predictions by learning from many species, a benefit rarely tested against matched single-species networks in new regions, where predictions matter. We pretrained neural networks on other species, fine-tuned them to each target, and compared them with identical networks trained only on the target and with conventional models, using Tasmanian mammals, mainland mammals transferred to Tasmania, and 157 birds evaluated in withheld bioregions. Pretraining slightly improved within-region discrimination for mainland mammals and birds (AUC +0.006 to +0.009), but the gain vanished or reversed in new regions (birds −0.0004; mammals −0.016). In withheld bird regions, target-only networks still beat conventional models (+0.003), and neural–conventional ensembles gained most (+0.010). Rankings also depended on evaluation extent and on how negative observations were defined. Claims that learning across species helps should be tested against target-only twins, in the regions and with the observations where models will be used.
