# What would distinguish architecture limits from data limits?

29 September 2026, Australia/Hobart. Astra's response to Barry's question,
prepared for discussion with Fable after the accepted Goal052 inner results.
These are proposals for a separate experiment, not changes to the authorized
outer assessment.

## What the present result says

The practical conventional margins are small: mean AUC +0.003390 for the common
73 targets and +0.000938 for the other 84. This constrains the claim that the
tested transfer approach substantially improves full-data discrimination over
the tuned benchmark. It does not establish equivalence, an irreducible noise
ceiling, or failure of deep learning generally. Transfer still improves on the
matched target-only network, and the within-species learning curves show a
data-efficiency benefit. Artificial subsampling of widespread species does not
stand in for naturally restricted species.

The selected conventional benchmark itself comprises 51 random forests, 66
histogram gradient boosters and 40 shallow neural networks at the full-data
endpoint. This is a comparison against a tuned learner panel, not a clean
contrast between neural and non-neural modelling.

The four screened architectures are one residual-MLP family, varying depth,
width and bottleneck. They share loss, optimiser, learning rate, regularisation
and input representation. The input has 24 raw variables: 19 bioclimatic
variables, elevation mean and SD, and vegetation, soil and land-use categories;
standardisation and one-hot encoding produce 103 columns. The model receives
cell-level summaries, not habitat images, seasonal sequences or neighbourhood
geometry. A narrow winner-versus-runner-up gap within this family cannot show
that all useful architectures have been exhausted, nor bound selection bias.

The response collapses accepted 2001–2025 records into presence in a 0.01-degree
cell. The contrasting class is effort-supported target-group background.
Missing environmental information, temporal aggregation, sampling and detection
processes, finite effective sample size, and model approximation can all limit
prediction. These are different explanations; the current experiment does not
separate them. A complex model cannot recover information absent from its inputs,
although it might make better use of information that is present.

There is a useful reason to expect this pattern: at prediction time the learned
representation is still a transformation of the same environmental inputs.
Auxiliary species supply training information about how to use those inputs;
they do not supply new observations of habitat at the target location. As target
training data become abundant, a strong single-species learner can catch up.
That is consistent with the declining transfer advantage along the learning
curve, without proving that the environmental representation is sufficient.

## Three discriminating tests

| Question | Smallest useful comparison | What a positive result would establish |
|---|---|---|
| Is the current learner leaving usable signal behind? | Same rows, predictors and spatial splits; current ResMLP versus a small prospectively chosen panel of different tabular learners, with matched target-only and multi-species versions where supported | Headroom within the existing representation and observation definition |
| Are the cell summaries losing habitat information? | Original features versus multi-scale habitat/context features, with both neural and strong conventional learners receiving comparable added information | Value of richer representation; a neural-specific advantage requires an architecture-by-input interaction |
| Are the occurrence/background labels obscuring the ecological signal? | A matched subset with repeat visits, complete checklists or independently recorded survey effort, evaluated against survey-supported outcomes | Evidence that the observation process matters; estimating detection needs identifiable survey information |

For the first test, an ensemble-based tabular model such as TabM is a credible
candidate, with one feature-token/attention model as a contrasting inductive
bias. TabM's benchmark shows that relatively simple ensemble-based MLPs can be
competitive with more elaborate tabular architectures; attention is not an
automatic upgrade. Its published results motivate a candidate, not a prediction
of success here. [Gorishniy et al., ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/c1ba41c694834aeef91ae161711d4939-Abstract-Conference.html).

Use equal search budgets, nested spatial selection, paired seeds and explicit
ensemble-compute accounting. Cross architecture with pretraining so an improved
target-only learner is distinguishable from stronger transfer. Retain the tuned
conventional benchmark. A tabular foundation model could be an additional
benchmark, but its external pretraining and scale constraints change the
question; it is not automatically a like-for-like multi-species treatment.
[TabPFN-2.5 technical report](https://arxiv.org/abs/2511.08667).

A smaller transfer-specific hypothesis is worth testing before a large new
architecture search: train the output layer first, then unfreeze the trunk.
The present design compares a permanently frozen trunk with immediate full
fine-tuning, so it does not isolate this intermediate strategy. Work in other
domains shows that such staged fitting can help under distribution shift.
That is a mechanism to test, not an explanation already established for
*C. erythrops*. [Kumar et al., ICLR 2022](https://arxiv.org/abs/2202.10054).

For the representation test, begin with multi-scale neighbourhood summaries of
existing layers, then consider time-matched remote-sensing patches if justified.
Keep the response rows fixed, include original-only and added-context ablations,
and account for patch extent when separating spatial training and validation.
Satellite-assisted SDMs show that this is a credible source of new information,
but results for European plants do not establish transfer to these Australian
birds. [Dollinger et al., Sat-SINR, 2024](https://isprs-annals.copernicus.org/articles/X-2-2024/41/2024/).

For observation-process work, donor richness alone is not a substitute for
repeat-visit detection data. Target-group background addresses some sampling
bias but does not turn non-records into verified absences. A more flexible
learner might otherwise fit reporting patterns more effectively without
improving ecological inference. [Phillips et al., 2009](https://doi.org/10.1890/07-2153.1).

## Priority and interpretation

My working expectation is diminishing returns from making the same tabular
ResMLP larger. I would first run a bounded, genuinely different same-input
comparison and staged-transfer test; that is the cheapest way to challenge an
architecture explanation. Richer habitat context and better observation data
may offer larger ecological gains, but that is a hypothesis, not a result.

Convergence among a few more learners would narrow the remaining headroom for
these inputs and labels. It would still not estimate Bayes error or prove an
inherent signal-to-noise ceiling. High AUC on restricted species is also not
proof that all ecological information has been recovered: the sampled
background and geographic extent help define that discrimination task.

Complete the frozen outer assessment first. Any later model exploration needs
its own prospective selection/evaluation design; once NCP/SEH/NNC outcomes have
been examined, they cannot serve again as an untouched confirmatory test for
models motivated by their results. The already examined other 84 species are
not a fresh validation set either.

Fable is asked to rank the competing explanations, identify the most informative
small experiment, and challenge this priority order. Agreement between us would
guide experiment design, not validate the hypotheses.

Local evidence: `Results.md`, `fable-review-20260927.json`,
`config/goal052_seawfb_dsdm.json`, `config/goal051_seawfb_conventional.json`,
the Goal049 response definition and the Goal050 predictor/transform contract.
