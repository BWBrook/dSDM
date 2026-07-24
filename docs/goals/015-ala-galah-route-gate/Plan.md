# Plan: Goal 015 ALA Galah Route Gate

1. Verify clean `main` at the authorized baseline and preserve Goal 014
   unchanged.
2. Pin `galah-python==0.13.3`; validate the corrected package-owned route,
   exact query, broad-intake switch, projection semantics, live caps, temporary
   config, and privacy contract.
3. Prove the runner synthetically, including one-call caps, configuration
   cleanup on success and failure, raw replay, mutations, leakage guards, and
   rejection of pass claims without raw.
4. Run one high-level count. Save the exact returned count DataFrame before
   interpretation and stop unless `totalRecords` is exactly 17 and within
   1--100.
5. Run one 900-second-bounded occurrence call only after the count gate. Save
   the exact returned DataFrame before schema interpretation.
6. Require every non-assertion core header literally except the one documented
   `dwcHeaders=true` alias from requested `license` to returned
   `dcterms:license`.
7. Generate privacy-safe tracked evidence, replay both ignored raw CSVs, run
   focused and full validation, and stop after this Goal 015 decision.

## Stop rules

Stop without a second live attempt on HTTP/access error, package or route
drift, count drift, timeout, wrong return type, row-count mismatch, material
schema failure, unsafe raw footprint, checksum drift, or privacy leakage.
