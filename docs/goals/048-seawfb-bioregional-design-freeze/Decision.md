# Decision

## Status

**Goal 048 v1.1 reached and passed the aggregate-canary compute checkpoint.
No bioregional holdout has been selected.**

The three-region SEAWFB design remains scientifically unchanged. The existing
15-region prospective rule, required complete BBS geometry, Tasmania training
role, species ecology, seasonal policy, response-free roles and scores, 50 km
buffers, joint selector, `X=10`/`X=20` rules, estimability thresholds, leakage
firewall, and evaluation metrics all remain frozen as specified.

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

## V1.1 engineering decision

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

## Checkpoint boundary

The four count-free freezes, offline serializer proof, and one aggregate
canary are complete. This checkpoint authorises no further occurrence access.
The sequential census runner and restart/failure-recovery checks are now
implemented but have not been executed. A separately authorised live run must
use the explicit galah 0.13.6 overlay, enforce the observed 10,000,000-group
ceiling cumulatively, and still stop before scoring if transport conservation
fails for any species.

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
canary therefore passes. The next tranche should run the sequential census on
`deep-server` under `tmux`, stopping immediately if the observed cumulative
group count reaches 10,000,000.
