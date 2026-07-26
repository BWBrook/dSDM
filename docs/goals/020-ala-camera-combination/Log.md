# Goal 020 log

## 2026-07-26 — implementation

The corrected and reaccepted Goal 019 island matrix was treated as frozen
upstream state. Goal 020 does not modify Goals 018 or 019.

Test-first RED command:

```sh
PYTHONPATH=src uv run --locked python tests/test_ala_camera_combination.py
```

The initial run exited 1 at import with the expected failure:

```text
ModuleNotFoundError: No module named 'dsdm_phase1.ala_camera_combination'
```

After the minimal implementation, the production reconciliation emitted
12,868 species-cell rows: 10,708 final presences and 2,160 retained
survey-supported absences. The five source categories are 6,417 ALA-only
presences, 4,113 camera-only presences, 165 presences in both sources,
13 ALA-presence overrides of camera absence, and 2,160 retained camera
absences.

The source union contains 178 overlapping species-cell keys and 5,407 unique
physical cells. It retains 651 within-camera conflicts and 1,221 ALA
low-cell-certainty placement flags as source metadata. There are zero centroid
mismatches and zero accepted-presence conflicts with the corrected island
matrix. The ignored private output SHA-256 is
`17a0544247891b0a3f765efcd38bf1ddf348ee6bc96af69e1f76319dbe6e668d`.

Final verification results are recorded below after the acceptance sweep.

## 2026-07-26 — acceptance sweep

One focused self-review found two material fail-closed improvements: Goal 020
now independently requires the exact Goal 018 and Goal 019 private-output
footprints, and tracked privacy validation rejects identifier-shaped payload
keys as well as leaked values. The private output was regenerated after this
repair and remained byte-identical.

Final checks:

- Goal 020 focused tests: 10/10 passed.
- Goal 020 tracked-only validation:
  `goal020_tracked_evidence_valid_private_replay_required`.
- Goal 020 full byte and semantic replay:
  `goal020_ala_camera_combination_complete`, 12,868 rows.
- Goal 018 focused tests: 23/23 passed.
- Goal 019 focused tests: 18/18 passed.
- Goal 018 full raw/private replay:
  `goal018_spatial_normalization_complete`.
- Goal 019 full private replay:
  `goal019_camera_spatial_normalization_complete`.
- Full Python discovery: 175/175 passed.
- JSON parsing, `py_compile`, `uv lock --check`, `git diff --check`, exact
  footprints, regular-file and symlink checks, private ignore status, tracked
  path inspection, and aggregate privacy checks passed.

Final SHA-256 identities:

- Goal 020 plan:
  `b54f375063fb6d071b395a799be7859e484cb21a419b6f77a9615e24cb3d33e6`.
- Private combined grid evidence:
  `17a0544247891b0a3f765efcd38bf1ddf348ee6bc96af69e1f76319dbe6e668d`.
- Tracked evidence manifest:
  `68f8623c0b496fe83882bc84ac4de30140c5b771e3c8863a1d17b23ed6d8e79c`.

The goal stops at evidence reconciliation. No pseudoabsence, predictor,
partition, mapping, modelling, legacy comparison, manuscript work, commit, or
push was performed.
