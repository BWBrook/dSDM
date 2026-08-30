# Log

## 2026-08-30 - implementation and canary

- Added Goal 046 config and mainland-only correction module.
- Bound the tracked Goal 045 config, summary, source, and training source by digest. New receipts bind the Goal 046 source/config identity and retain the Goal 045 numerical seed authority; no Goal 045 private checkpoints are reused.
- Read the existing `other_species_count` field locally from the mainland response substrate so the strict rule can be applied without modifying shared row helpers or raw data.
- Focused tests: 16 passed. Input validation: passed with mainland assignment 1,053,032 rows and 20 response heads; Tasmania access remained `0/0`.
- The bounded CPU canary completed in approximately 62 seconds wall-clock (10.5 seconds recorded fit time) at two epochs. It exercised 19 strict auxiliary heads, all four target arms, 10,941 target training rows, and 2,450 held rows for *Dasyurus maculatus*.
- Canary strict diagnostics removed 3,982 auxiliary background rows from the
  277,571 original rows for that target/fold; this is not a unique-cell count.
  No auxiliary presence rows were removed. Production was not launched.

## 2026-08-31 - production complete and independently validated

- Independent `validate` exited `0` with status `goal046_ready`, covering five
  fraction100/full endpoints and 125 final fold-seed tasks. The detached shell
  did not leave a `run.exit` marker; the completion log and independent replay
  validator are authoritative, and the missing marker is a non-scientific
  wrapper anomaly.
- Production created 25 strict q surfaces, five strict-q conventional caches,
  175 pretraining receipts, 75 selection receipts, 125 final receipts, and
  500 target fits. The runtime line was 5,478.552 seconds.
- Sums of fold/head-specific strict auxiliary background-row removals across
  five folds were Dasyurus `20,370`, Notamacropus `133,273`, Pseudocheirus
  `207,647`, Trichosurus `317,107`, and Vombatus `184,002`. These are not
  unique-cell counts; cells can recur across held folds and response-head
  constructions. Zero auxiliary presences were removed.
- `bridge_control` was reselected with mean rank `1.4`. Corrected full-target
  dSDM mean-fold AUC was higher than target-only learning for four of five
  targets, q-neural for all five, and the best conventional comparator for all
  five; strict-q conventional was higher for four of five. Paired seed-target
  contrasts were positive in 21/25 and fold-ensemble contrasts in 20/25. These
  are descriptive, not inferential replication counts; the result is mainland
  development evidence only.
- Goal 045's fraction100/full result is superseded because its auxiliary
  support was not strict leave-target-out. Tasmania remains sealed at `0/0`;
  the next boundary is a prospectively frozen one-shot transfer assessment.
- Final verification: the focused suite passed 16 tests; the repository-wide
  suite returned 704 passed, 2 failed, 2 skipped, and 254 subtests. Both
  failures are `tests/test_dsdm_outer_ready.py` from the pre-existing Goal037
  `model_adapters` binding digest mismatch recorded at Goals044-045. Goal046
  did not modify that config or module, so this is not a Goal046 regression.
