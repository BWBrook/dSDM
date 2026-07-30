# Goal029 Conventional Baseline Production Design

## Purpose

Scale the accepted Goal028 modelling foundation from a bounded engineering
preflight to the complete conventional Tasmanian panel while retaining a
sealed outer assessment and making a long run exactly resumable.

## Architecture

The production plan has three layers:

1. **Leaf execution.** One leaf is one candidate seed across all five inner
   assessment folds. It produces one complete OOF score per permitted
   outer-training row or one blinded failure receipt.
2. **Family reduction.** Seed leaves are merged only when their RowKeys,
   labels, folds, subset/encoder provenance, and required seed set match.
   Complete candidates compete within one species × endpoint × family.
3. **Selected refit.** The winning candidate is refit once per required seed
   on its permitted outer-training endpoint, serialized, and replayed on a
   response-free challenge matrix. No held row is requested.

Subset membership is stored as separate content-addressed records for each
species × endpoint × split. The five fold-specific `E_v` memberships and the
outer-training refit membership are not collapsed into a species-endpoint
bundle. Leaf identity references all six records and family-specific encoder
digests.

## Failure model

Candidate failures are local but decisive. A single failed fold or seed
invalidates that candidate and hides all partial performance. The mandatory
null and conservative anchors prevent a family from surviving only through
fragile candidates. A tunable family also needs a second complete candidate.
Once selected, a model cannot silently fall back to the runner-up.

Warnings are classified data. Only the named pyGAM deprecation and valid ANN
maximum-epoch status are accepted. Unknown warning text stops rather than
being normalised away.

## Resumption and provenance

Leaf checkpoints are content addressed from a controlled digest of all
`src/dsdm_phase1/*.py` modules plus config/lock, runtime/host, upstream
authority, task, split memberships, and encoder state.
A temporary sibling is fully written, validated and fsynced before atomic
rename. Resumption loads only an exact identity match; mixed trees, runtimes,
hosts, or upstream products cannot be combined.

The canonical reducer order is independent of worker completion order.
Parallel workers share no mutable model state. Import-time environment caps,
a retained live `threadpoolctl` limiter, and explicit PyTorch intra/inter-op
limits enforce one numerical thread in every parent and child process. Policy
and effective evidence are bound into execution/checkpoint provenance. One
host owns a canonical run.

## Validation and publication

While still staged, artefact-only validation recomputes every plan identity,
seed set, subset, metric, threshold, selection, model digest, challenge
replay, privacy rule, and outer counter. A subsequent fresh cache-disabled
source audit reruns exactly 359 deterministically selected leaves, including
one per family stratum and coverage of every candidate and seed. Its receipt
reconciles the exact valid-result or invalid-failure state of every selected
leaf.

Private and tracked trees first receive core manifests. One acyclic pair
descriptor binds both core digests and the transaction ID. Only after staged
validation and source audit pass are the directories renamed as a pair; the
final marker binds the pair-descriptor digest and is written last. Consumers
reject missing, partial, mismatched, unmarked, or extra-file pairs. A failed
rename or marker write restores the complete trees to their stage paths where
possible and never deletes the only authoritative copy.

## Compute decision

Calibration first proves four zero-fit spawned children obey the numerical
thread policy. Two frozen valid `gam01` leaves then act as a workers-1/2
canary; semantic disagreement, invalidity, unsafe memory/swap state, or a
workers-2 slowdown above `1.25` stops the run. The exact 30-leaf
representative panel then spans all species, endpoints, families, candidate
extremes, and seeds at workers 1, 2, and 4. Among trials with 6 GiB
free-memory headroom and no swap growth, the smallest count within `1.10` of
the fastest safe wall time is selected. The 32-leaf GAM fragility panel runs
once at that setting.

This is 126 leaf executions and at most 735 estimator fits. Exact
`threadpoolctl==3.6.0` is runtime-checked from the existing scikit-learn lock
closure rather than changing Goal028's frozen dependency manifests.
