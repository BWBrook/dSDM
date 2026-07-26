# Log

## 2026-07-26 — RED

Before implementation, the Goal022 test module could not import the extraction
module and no production plan or output existed. This was the intended RED
test-first checkpoint.

## 2026-07-26 — GREEN

Implemented the rasterio extraction gate, deterministic Float32 CSV serializer,
source bindings, privacy-safe evidence, atomic publication, and synthetic
contract tests. Full replay matched both private CSVs and all tracked evidence;
the aggregate oracle matched the frozen counts.

## 2026-07-26 — acceptance repair

Added strict semantic validation before the full-replay branch so a tampered
payload cannot pass merely by refreshing its manifest checksum. Expanded
contract tests cover portable tracked validation, semantic/privacy/footprint
tampering, private-output replay, plan drift, destination guards, and atomic
rollback. Removed the unused `--validate` CLI option.

## 2026-07-26 — runtime portability correction

Source provenance now records the frozen lock-matrix contract (`rasterio 1.4.4`,
NumPy 2.4.6 for Python <3.12 and 2.5.1 for Python >=3.12) rather than the
current interpreter's NumPy version. Evidence was regenerated; private CSV
bytes and hashes are unchanged.
