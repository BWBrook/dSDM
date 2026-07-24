# Goal 017: ALA nine-species acquisition

## Objective

Run one bounded, fail-closed live workflow: nine canonical Tasmania counts,
one bounded 2001 `recordID` canary, and—only if every gate passes—nine full
canonical occurrence downloads. The estimand is ALA-indexed records matching
each exact parent query at retrieval time.

## Boundaries

The runner uses `galah-python==0.13.3`, the corrected package-owned endpoint,
and `use_data_profile=False`. It never requests aliases or child branches,
normalises or filters rows, retries calls, retains row values in tracked
evidence, or performs camera/manuscript work. Goal016's raw-backed decision is
required before the live run; provider identity is calibrated by this canary.

No live call was made while constructing this scaffold.
