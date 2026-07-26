# Goal 021 log

## 2026-07-26 - test-first RED

Goal 020 at commit `77a4641f5aa550650c986b25587a79dc04607fe7` was
treated as frozen upstream state. Goal 021 does not modify Goal 020 or inspect
raw camera inputs.

The Goal 021 focused test was created before the implementation module. The
required RED command was:

```sh
PYTHONPATH=src uv run --locked python tests/test_pseudoabsence_derivation.py
```

It exited 1 at import with the expected missing-feature failure:

```text
ModuleNotFoundError: No module named 'dsdm_phase1.pseudoabsence_derivation'
```

No production module or private Goal 021 output existed when this RED was
recorded.

## 2026-07-26 - implementation and focused repair

The initial arithmetic interpretation (335 candidates) was rejected; the
frozen stage-A interpretation yields 2,316 candidates and 587 accepted
pseudoabsences. The repaired implementation preserves candidate centroids and
support/nearest-source provenance, uses the explicit GRS80 UTM55S pipeline
(EPSG:7855), validates Goal020 full replay and decision-bundle bindings, and
publishes staged outputs atomically. Production generated the two ignored
private CSVs and six aggregate evidence files. The stop boundary remains
before thinning, weighting, balancing, predictors, partitions, mapping, and
modelling.

Final acceptance rerun: Goal021 focused 10/10, Goal020 focused 10/10, full
discovery 185/185, tracked validation with private output unavailable, full
semantic replay, JSON parsing, py_compile, `uv lock --check`, and
`git diff --check` all passed. Private output hashes remain 58f3bd...778b3ec
(audit) and e67298...0616a3 (response); accepted-key and 40,990-byte
distance-preimage hashes remain frozen. Evidence payloads carry output
byte/SHA/schema provenance and are compared semantically during full replay.
