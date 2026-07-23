# Goal 014: ALA Offline Download Gate

## Objective

Validate the bounded direct-API asynchronous occurrence-download route with one
small positive species-year selector. This is route validation only; it is not
full acquisition or ecological analysis.

## Current state

`blocked_submission_http_403_no_job_handle_observed`. The count selector found 17
records for the accepted *Pseudocheirus peregrinus* concept in Tasmania in
2001, but one operator-reported GET attempt returned HTTP 403 before a job or
status handle was retained. No causal attribution is made and no retry is
permitted.

The current OpenAPI documents the asynchronous route and status schema but does
search has a 5,000-result depth cap, and the pinned offline source default
maximum is 100,000,000. Production operability is nevertheless
`unverified_http_403` and the deployed offline maximum is unknown.

## Boundaries

- One count-only selector and at most one GET submission.
- Runtime email is never tracked; no credentials, JWT, POST, notification, DOI,
  camera data, or full-species download.
- Raw material is confined to the ignored Goal 014 directory.
- No staging, commit, push, cleanup, or movement outside authorized paths.
