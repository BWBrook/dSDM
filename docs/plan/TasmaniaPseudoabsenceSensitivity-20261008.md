# Tasmania pseudoabsence-removal sensitivity: approved execution

## Authority and scope

At 23:28 AEDT on 8 October 2026, Barry instructed: **“All seven endpoints.
Proceed.”** This approves the protocol-wide option in
[the reviewed proposal](TasmaniaPseudoabsenceSensitivityProposal-20261005.md).
The earlier proposal is retained as the record of the pre-approval alternatives.

The sensitivity covers all eight Tasmania species, both neural methods
(`target_only_resmlp`, `multihead_full_finetune`) and the primary-selected
conventional candidate for each species and endpoint. The endpoints are:

- `fraction25/ladder00`, `fraction25/ladder01`, `fraction25/ladder02`;
- `fraction50/ladder00`, `fraction50/ladder01`, `fraction50/ladder02`;
- `fraction100/full`.

The planned production inventory is 8,125 physical fits: 6,160 neural and
1,965 conventional. The fixed real smoke cases remain those in the reviewed
proposal (14 executions, all at `fraction100/full`, non-promotable).
Candidate-level inventory and fit counts will be verified before launch.

For every endpoint, pseudoabsences are removed from target discovery,
stopping, replay and outer-fitting roles by canonical row ID. Original subset
membership and all evaluation rows remain fixed. Thresholds are recomputed
from the sensitivity OOF predictions separately for each species, method and
endpoint. Conventional candidates are frozen to the corresponding original
endpoint selection. Accepted auxiliary states, `q`, map transforms, seed
policies, neural architecture and training rules are unchanged.

The map comparison remains exactly 24 pairs at `fraction100/full`, using the
71,023-cell structural domain and the rank, displacement and top-decile rules
in the reviewed proposal. All seven endpoints receive the paired fixed-panel
performance comparison. The optional survey-only evaluation view remains
excluded. Source-specific specificity with denominators is included as agreed.

This implements a prespecified sensitivity question with post-opening choices
about filtering, thresholds, comparator selection and map summaries. It is
not a fully prospective confirmatory test.

## Execution gates and stopping rule

1. Bind the original archive and accepted data/configuration/receipt digests.
   Join canonical Goal025 source identity to the original model memberships.
2. Before any fit, count both classes and absence sources separately for every
   discovery, stopping, replay and outer-fitting role across all seven
   endpoints. Establish evaluation membership without reading held responses.
3. Independently review the filter, manifest and relevant synthetic checks;
   qualify the fixed repeated real smoke in the historical runtimes.
4. Run the complete panel only after these gates pass. Close every prediction
   before held-response access and scoring, then independently replay the
   paired metrics and map summaries.

**A missing class in any required role aborts the entire panel before fitting.**
Do not substitute endpoints, merge roles, pool folds, restore pseudoabsences,
change weighting, or score a partial panel. Such a failure is a scientific
consultation trigger under the accepted proposal, not permission to redesign
the sensitivity silently.

No sensitivity fit, new held-response access, score or map prediction has
occurred. New artifacts use a separate
private root under `data/processed/dsdm/tasmania-pseudoabsence-20261008/` and
aggregate evidence under `evidence/tasmania_pseudoabsence/20261008/`.

The existing manuscript and original assessment remain the accepted baseline.
Source changes and reporting from previous work remain uncommitted; this
approval does not request publication, push or a new message to a person.

## Pre-fit result and remaining boundary

The [source census](../../evidence/tasmania_pseudoabsence/20261008/source-census.json)
passes. It reads the 11,039 outer-training response rows after verifying the
response-free allowlist and every source binding; it excludes held-response
payloads. All 280 inner and 56 outer endpoint membership digests match the
accepted original bundles. All 896 separate roles retain both classes after
exact pseudoabsence subtraction.

| Role | Memberships | Minimum retained absences | Minimum retained presences |
|---|---:|---:|---:|
| Discovery | 280 | 11 | 35 |
| Stopping | 280 | 2 | 7 |
| Replay | 280 | 14 | 51 |
| Outer fit | 56 | 23 | 75 |

The two minima in a row are calculated separately; they need not belong to
the same membership. Small stopping-set counts remain a limitation despite
passing the binary class-support gate. No fold or endpoint has been changed.

An independent implementation of the original ladder ordering reproduced all
336 accepted membership digests and every baseline/retained/excluded source
count, class count and identity-set hash across the 896 roles. Eight focused
tests pass, including altered-input refusal and opaque held-payload handling.
The census binds bundle metadata using the original recorded array digests;
it does not qualify numerical model arrays or the fitting implementation.

The [availability audit](TasmaniaAuxiliaryAvailability-20261008.md) identified
a defect in the earlier proposal's execution assumption: Goal035 saved hashes
and epochs for its 200 required inner multi-head states, but no loadable
weights. The 40 outer states exist and match their receipts. They cannot
replace the inner states because their training memberships differ.

**An amendment is awaiting Barry's decision:** permit 200 deterministic
replay-only reconstructions at the already recorded epochs, requiring exact
original initialization, shared-state, complete-state and auxiliary prediction
hashes before any sensitivity target fit. Preserve original memberships,
inputs, source and runtime. Do not repeat discovery, choose new epochs,
reconstruct pooled models or fit `q`. Any mismatch stops the reconstruction.
This would bring physical execution to 8,339 (8,125 target production + 14
smoke + 200 recovery), with the target panel unchanged.

This explicit decision is required by the approved proposal's rule that
“no auxiliary refit or new `q` estimate is permitted.” Source inspection
supports the recovery route; empirical recovery remains untested. Source
census success is not production qualification. Preparation is complete to
this boundary, and no fitting has begun.
