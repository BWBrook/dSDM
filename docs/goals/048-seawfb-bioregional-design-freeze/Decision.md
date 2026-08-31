# Decision

## Status

**Goal 048 v1.3 is complete. The frozen simultaneous outer assessment is NCP
(supported geographic transfer), SEH (environmental edge), and NNC
(fragmented/land-use mosaic).**

Each complete region plus its external 50 km buffer is excluded simultaneously
from model development. Tasmania is ordinary training geography. The original
15-region candidate rule, complete BBS geometry, species ecology, seasonal
policy, response-free roles and scores, `X=10`/`X=20` rules, estimability
thresholds, leakage firewall, and evaluation metrics remain unchanged.

## Final scientific resolution

The immutable response-free ranking contained 147 sets and 109 passed every
hard gate. Ranks 1 and 2 failed only because AUA had 937 `X=10`
effort-supported cells, below the frozen 1,000-cell candidate minimum. The
first feasible set, immutable rank 3, was NCP/NET/SEH: minimum score
0.6906158357771262, score sum 2.288332635106829, and 39 conservative common
targets. The runner-up, immutable rank 4, was NCP/NNC/SEH: minimum score
0.6851173020527859, score sum 2.362327188940092, and 40 common targets.

The signed rank-3-minus-rank-4 margins are +0.005498533724340282 in minimum
score and -0.07399455383326314 in score sum, so the prespecified ambiguity rule
fired and execution stopped. An independent audit recommended rank 4: relative
to rank 3 it gains 0.0080645161290322 in the edge role and
0.0714285714285715 in the mosaic role for a supported-role loss of only
0.005498533724340282. Barry explicitly accepted that scientific trade-off on
2026-08-31.

This was an authorised resolution of a frozen ambiguity, not a revised
ranking, post-hoc response score, or occurrence-magnitude tie-break.
Occurrence evidence remained pass/fail only. The frozen design is therefore:

- NCP - Naracoorte Coastal Plain: supported geographic transfer;
- SEH - South Eastern Highlands: environmental edge; and
- NNC - NSW North Coast: fragmented/land-use mosaic.

The conservative primary panel contains 40 seed targets. The `X=20`
evaluation-only diagnostic passes for 34 of those 40 and does not redefine the
primary panel.

## Incident disposition

The premature two-identifier union/species-facet probe is recorded in the
compact tracked incident receipt. Its counts cannot enter a formal transport
gate, species inclusion or role, region score, ranking, support gate,
estimability result, or scientific interpretation. *Acanthiza pusilla* and
*Pardalotus punctatus* remain mandatory feasibility seeds and cannot be pruned
or reclassified because their counts were exposed.

No inference can be drawn from the discrepant union and facet totals because
the two taxa were not separately queried and the exact request/response
envelopes were not retained. No occurrence row or model outcome was produced.

## Frozen geometry and engineering decisions

The literal official-land overlap rule admits AUA, BBS, KAN, NAN, NCP, NET,
NNC, NSS, SCP, SEC, SEH, SEQ, SVP, SYB, and VIM. EYB is excluded at
approximately 0.6678 overlap, below 0.80; this corrects the expected count
without changing the selector. BBS01, BBS03, and BBS28 remain the sole
admitted-region completion.

The Rainbow Lorikeet feasibility seed uses current accepted
*Trichoglossus moluccanus*. The obsolete submitted name *T. haematodus* is
retained as provenance, while the composite pre-split alias
*T. moluccanus/rubritorquis* is excluded because it is not attributable to one
biological species.

The feasibility route will use only server-side aggregates, one biological
species at a time. Its exact frozen ordered identifier union includes the
accepted species parent, reviewed accepted descendants/subspecies, and
necessary reviewed historical aliases attributable to that species;
cross-species unions are forbidden. Under the identical ordered union and
filters, a separate total must equal the sum of `lat_long` facet counts
exactly. Coordinate groups are snapped immediately to the 0.01-degree grid,
collapsed to unique species-cells, bound to a private checksum receipt, and
then discarded. A mismatch, truncation, timeout ambiguity, missing coordinate,
malformed facet, or transport-ceiling failure stops the goal. Occurrence-row
download and raw-row fallback are prohibited.

Aggregate species-cell evidence may only pass or fail the prespecified
`X=10`, `X=20`, and estimability gates. Candidate-role scores and rankings
remain entirely response-free.

The 100-name ledger is a mandatory, response-blind feasibility seed, not the
final pretraining-universe ceiling. The sequential transport census queries
the 96 effort-eligible members in frozen order; Ceyx azureus, Fulica atra,
Haliaeetus leucogaster, and Spilopelia chinensis remain in the ledger with
status `not_queried_frozen_role_exclusion` and their frozen exclusion reasons.
Goal 048 uses eligible seed members for a conservative support and common-target screen. Goal 049 may expand all bird
universes under the same frozen taxonomic/ecological rules before canonical
acquisition and before holdout outcome access, but cannot change, substitute,
or re-rank the Goal 048 regions. More eligible donors can only relax support;
canonical Goal 049 data reconstruct final exact labels and panels.

## Completed census checkpoint

The four count-free freezes, offline serializer proof, aggregate canary, and
sequential census are complete. The census covered 96/96 effort species,
7,211,394 facet groups, 2,620,016 retained species-cell memberships, and
30,496,223 total occurrence counts. It retained zero occurrence rows and
produced zero model outcomes. Peak RAM was 937,869,312 bytes and private disk
use was 141,123,472 bytes. The four frozen role exclusions remain unchanged
and unqueried.

The census receipts remain private except for these high-level aggregates and
their digests. Occurrence evidence was permitted only for hard support and
estimability pass/fail gates; it could exclude infeasible sets but could not
score, rerank, or break ambiguity between feasible sets.

## Predictor and scoring completion

The portable predictor substrate is complete at exactly 1,144,286 rows: the
1,125,325 Goal 041 rows plus 18,961 BBS additions. Old rows and schema were
preserved exactly. The extension used local categorical sources, an aligned
native-grid ALA WCS WorldClim crop for the northern gap, and 29 exact GA elevation
blocks, with overlap proof and checksum-bound private receipts. Missingness was
1,523 rows for each BIO layer, 1,814 for NVIS, 41 for soil, and zero for ALUM
and elevation. The extension read zero response inputs.

Response-free scoring used the fixed continuous-complete PCA basis, all 455
unordered triples and 1,365 member values, simultaneous retained complements,
average-tie percentiles, mapped-mapped rook-edge fragmentation, global-level
ALUM entropy, and EPSG:3577 50 km tiles anchored at `(0,0)`. The training
spatial-fold gate is explicitly the number of distinct anchored 50 km support
tiles per class.

All later transforms, pseudo-background generation, internal spatial CV,
tuning, early stopping, thresholds, architecture choices, target subsampling,
and fitting are confined to retained training geography. ROC AUC is primary;
balanced accuracy, TSS, MCC, sensitivity, and specificity are diagnostic and
use thresholds frozen from training-only OOF predictions. Goal 049 may expand
the bird universe but cannot rerank or substitute the three regions.

No model fitting, prediction, thresholding, holdout-outcome access, manuscript
revision, commit, or publication claim occurred during the scientific design
selection itself.

## Aggregate-canary decision

After all four count-free freezes validated, the formal *Acanthiza pusilla*
canary conserved 649,432 records exactly across 136,829 `lat_long` groups and
collapsed to 50,736 exact-domain species-cells. Runtime was 13.454 seconds,
peak process RAM was at most 508,329,984 bytes, and private Goal 048 disk use
was 94,763,052 bytes. The canary therefore passed the per-taxon, conservation,
RAM, disk, missing-coordinate, and runtime gates.

The conservative linear 100-seed projection is 13,682,900 groups; the
role-filtered 96-seed projection is 13,135,584 groups. Both are
capacity-planning diagnostics, not prespecified ecological or transport gates;
the 10,000,000 ceiling applies to the observed cumulative full census. The
canary therefore passed. The subsequent sequential census completed under
the same one-species-at-a-time contract; its high-level result is recorded in
the completed census checkpoint above. The observed cumulative group ceiling
remained fixed at 10,000,000.
