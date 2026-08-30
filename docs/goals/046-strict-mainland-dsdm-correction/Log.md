# Log

## 2026-08-30 - implementation and canary

- Added Goal 046 config and mainland-only correction module.
- Bound the tracked Goal 045 config, summary, source, and training source by digest. New receipts bind the Goal 046 source/config identity and retain the Goal 045 numerical seed authority; no Goal 045 private checkpoints are reused.
- Read the existing `other_species_count` field locally from the mainland response substrate so the strict rule can be applied without modifying shared row helpers or raw data.
- Focused tests: 13 passed. Input validation: passed with mainland assignment 1,053,032 rows and 20 response heads; Tasmania access remained `0/0`.
- The bounded CPU canary completed in approximately 62 seconds wall-clock (10.5 seconds recorded fit time) at two epochs. It exercised 19 strict auxiliary heads, all four target arms, 10,941 target training rows, and 2,450 held rows for *Dasyurus maculatus*.
- Canary strict diagnostics removed 3,982 auxiliary backgrounds from the 277,571 original rows for that target/fold; no auxiliary presence rows were removed. Production was not launched.
