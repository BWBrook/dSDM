# Decision

## Status

Goal 043 is `ready` as of 2026-08-20.

## Spatial design

The bounded search evaluated 64 deterministic five-fold assignments at each
of 100, 50, and 25 km in EPSG:3577. No model, prediction, performance metric,
or Tasmania evidence entered selection.

The 100 km scale had no feasible assignment. Its dominant failure was loss of
adequate training presence for geographically restricted *Pseudomys fumeus*
and *P. shortridgei* when too much of their evidence fell in one large block.
The 50 km scale had 12 feasible assignments and the 25 km scale had 60. The
largest-feasible rule therefore selected 50 km, seed 0, with 558 blocks.

| Fold | Mainland cells | Share |
|---:|---:|---:|
| 0 | 207,366 | 19.69% |
| 1 | 208,375 | 19.79% |
| 2 | 207,079 | 19.67% |
| 3 | 216,124 | 20.52% |
| 4 | 214,088 | 20.33% |

These are scattered held spatial blocks, not five contiguous biogeographic
regions. That is suitable for mainland model development; Tasmania remains the
later hard geographic-transfer assessment.

## Split-authorised responses

The Goal 042 full-mainland table was used only as a conservative partition-
coverage diagnostic. It is not a model input. All 20 response heads were
rematerialised separately for each fold's training and validation roles using
only occurrence records assigned to that role. Thus a held target presence
cannot change a training cell's nearest-presence distance, and a held donor
record cannot contribute training support.

The ignored output contains 3,775,385 fold-role-target rows. Actual
rematerialisation passed the hard minima:

- shared-target validation presence: 183 cells;
- shared-target validation X=3 background: 75 cells;
- all-head training presence: 106 cells; and
- all-head training X=3 background: 311 cells.

X=2 and X=5 remain nested sensitivity flags. Target-group backgrounds remain
effort-supported candidates, not true absences or occupancy non-detections.

## Predictor transformations

Five fold-specific transforms and one reserved `mainland_full` transform were
fitted from continuous-complete mainland training-map cells. The transforms
use population-SD z-scaling for 21 continuous predictors and nominal
vocabularies for NVIS, Soil Order, and ALUM. `__MISSING__` and `__UNSEEN__`
remain distinct even when a fold did not observe categorical missingness.

Exactly 1,128 of 1,053,032 mainland map cells have continuous source nodata.
They remain in the audit substrate but are not modelable and are never
imputed. The worst whole target-class exclusion is five of 343
*Pseudomys novaehollandiae* presences (1.46%), below the frozen 2% gate. The
largest fold-specific proportion is also that species, two of 90 validation
presences in fold 3 (2.22%); this is descriptive and caused by the small
denominator, not by a different missingness policy.

All three categorical vocabularies were represented in every complementary
training fold, so inner validation requires zero `__UNSEEN__` mappings. The
sentinel remains reserved for genuine later geographic novelty.

## Firewall and privacy

Tasmania response rows read: zero. Tasmania predictor rows used: zero.
Tasmania did not enter block selection, response materialisation, transform
fitting, or diagnostics. The `mainland_full` transform is reserved for a later
final refit after mainland model development is frozen.

Cell assignments, split responses, and detailed diagnostics remain ignored.
Tracked files contain only exact transform parameters, aggregate counts,
checksums, rules, and the decision; they contain no cell IDs, coordinates,
donor-to-cell associations, or camera identifiers.

## Decision

Accept the mainland spatial-development substrate. The next boundary is a
mainland-only modelling protocol and compute preflight. Tasmania must remain
sealed until all method and hyperparameter choices are frozen.
