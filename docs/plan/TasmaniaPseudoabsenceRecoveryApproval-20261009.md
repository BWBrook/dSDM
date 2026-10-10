# Tasmania sensitivity: auxiliary recovery approved

On 9 October 2026 Barry instructed **“Approved, continue.”**, responding to
the request to recover 200 inner auxiliary states and continue the full
seven-endpoint Tasmania sensitivity. This resolves the recovery boundary in
the [8 October execution record](TasmaniaPseudoabsenceSensitivity-20261008.md).
The original eight-species, seven-endpoint sensitivity remains authorised.

The approved amendment is exactly 200 multi-head auxiliary reconstructions:
eight species × five inner folds × five original seeds. Use unchanged original
auxiliary data, memberships, masks, species ordering, architecture, historical
source/runtime and recorded replay epochs. Do not repeat discovery or select
new epochs. Do not reconstruct pooled models or fit `q`; those paths are not
used by the three selected sensitivity methods. Reuse the 40 saved outer
multi-head states directly.

Every reconstruction must match the recorded initialization, initial/final
shared state, complete model state and auxiliary replay prediction hashes.
All 200 must pass before sensitivity target fitting. A mismatch stops recovery;
no relaxed tolerance, new discovery or runtime substitution is authorised.
Retain failed-attempt evidence and fresh serialization hashes for recovered
weights, linked to the original tensor-state digests.

The approved inventory is 8,125 target-production fits, 14 fixed non-promotable
smoke fits and 200 auxiliary replay fits: **8,339 physical executions** if
successful without failures. Source census, independent implementation review,
smoke qualification, complete prediction closure before outer-response access,
and independent metric/map replay remain required. No additional stage-by-stage
permission is needed within this envelope.

The accepted preflight receipt is
`evidence/tasmania_pseudoabsence/20261008/verification.json`, SHA-256
`73fe43dc79f367826a4f877f57de1b10ac29e813b6a48fc6f7f45285aee8de23`.
Its historical `amendment_pending` status records the state before this approval.
The auxiliary availability audit has receipt digest
`765e45c7f567c1e021d5954ea69b7d6d0bd11c3863efff2c855e7780cd562347`.
Preserve those records and the original proposal. New execution evidence goes
under `evidence/tasmania_pseudoabsence/20261009/`; private artifacts stay in
the separate `data/processed/dsdm/tasmania-pseudoabsence-20261008/` run root.

Keep the historical three-worker, single-thread Mac neural lane and four-worker,
single-thread Linux conventional lane. Verify current capacity and set bounded
production limits from the fixed smoke measurements before launching the
target panel. Preserve all original fits, evaluation memberships and results.
