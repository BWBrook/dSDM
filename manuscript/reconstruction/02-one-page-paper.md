# Step 2: One-page paper

**Status:** draft v1, 12 November 2026. To be iterated with Codex, then reviewed by Barry.

---

## Learning from other species improves distribution models only where they were trained

**Introduction.** Conservation needs maps of where species live, most of all where records are sparse. Species distribution models (SDMs) draw these maps by relating records to environment. Deep learning offers an appealing upgrade: a neural network learns first from many species, then adapts to the species of interest, borrowing information its own records lack. Such models score well, but the same network trained on the target alone might score as well. The test that matters is prediction in new regions, where SDMs are put to use.

We asked whether learning from other species improves predictions in new regions, testing four predictions from theory:
1. Shared responses to environment make pretraining improve prediction where the model was trained.
2. The gain is largest when the target's own records are few.
3. The gain persists in new regions only if what is shared is general niche structure rather than features of the training region.
4. Shared observers make model rankings depend on how well recorded the negative observations are.

**Methods.** We used three Australian cases:
- eight Tasmanian mammals surveyed by cameras and assessed in five held-out patches;
- five mainland mammals transferred to Tasmania;
- 157 south-eastern Australian birds, 73 of them assessed in three whole bioregions withheld with 50 km buffers.

Inputs were climate and habitat summaries for each grid cell. For each target species we compared:
- a neural network (a multilayer perceptron, a standard deep-learning model) pretrained on other species and fine-tuned to the target;
- an identical network trained on the target alone;
- the best of four tuned conventional SDMs.

Targets were excluded from pretraining, and held-out regions from all fitting. We fixed primary models and scoring before examining held-out outcomes. We measured discrimination as the area under the receiver operating characteristic curve (AUC).

**Results.** Pretraining helped in familiar places. AUC rose by 0.009 for mainland mammals and by 0.006 for birds, with 72 of 73 bird species improving. The gain held when familiar places were scored over areas the size of the held-out regions (+0.007; 68 species improved). In new places it disappeared: −0.016 for mammals transferred to Tasmania, and −0.0004 for birds (34 species improved). Tasmanian mammals gained nothing from pretraining in either setting.

The pretrained network's lead over conventional models widened from 0.003 to 0.007 when target records were cut to a quarter, but among the least-recorded third of species it was only 0.0006.

In new bird regions both networks beat conventional models by 0.003; averaging either network with a conventional model gained 0.010. Absolute AUC fell from 0.83 in familiar places to 0.68 in new places; scoring familiar places over the smaller area alone gave 0.69.

Rankings tracked the evidence used for absence. The pretrained network led conventional models against poorly recorded background and trailed them against well-recorded background. In Tasmania, scoring against survey-confirmed absences alone turned its deficit (−0.005) into a lead (+0.015).

**Discussion.** What a network learns from other species stays where it was learned. In new regions, the network's small advantage came from the network itself, and ensembling with a conventional model was the larger and cheaper gain. Hypotheses 1 and 4 held; hypothesis 2 held under subsampling but not for the least-recorded species; the evidence favoured the second branch of hypothesis 3.

These conclusions rest on tabular inputs, small effects (below 0.01 AUC) and three cases that share Australian geography and some taxa. The Tasmanian survey-only analysis was added after the primary results. Networks that see imagery or spatial context may share more transferable information.

The test itself transfers to any taxon or region: any claim that learning across species helps should be measured against a single-species twin, in the regions and with the observations where predictions will be used. For practitioners, ensembles are the dependable gain. For data providers, recording where species were sought and not found would sharpen both the models and the tests that rank them.
