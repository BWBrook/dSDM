# Log

2026-07-27 — Implemented and repaired `src/dsdm_phase1/model_ready_features.py`,
generated the exact eight-file tracked evidence tree and two-file ignored
private footprint, and added focused tamper/API tests. The identity-bearing
API returns canonical IDs, 25 continuous float64 columns, and 3 nominal
categorical columns; it never returns a model matrix. Real frozen inputs
replayed at 71,023 map cells, 5,087 response cells, and 12,711 response rows.
Fit counts are 64,270 (`outer`), then 52,016, 53,231, 52,497, 50,449, and
48,887 for CV folds. Focused tests: 15 passed. Full suite: 251 passed, 4
warnings, 254 subtests. Final `--validate --full` invoked the Goal025 final
replay once and passed (`tracked_valid`, `private_valid`, `full_replay`). No
Goal024/025 files were modified. No commit or push performed.
