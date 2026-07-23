# Log: Goal 014 ALA Offline Download Gate

## 2026-07-24 - Preflight and bounded live attempt

- Working directory `/Users/bwbrook/papers/dSDM`; branch `main`; HEAD,
  `origin/main`, and required baseline all equal
  `204d37020ef2bad355940610b63f64c6e9a079c1`; status clean.
- One count-only selector was issued for accepted *Pseudocheirus peregrinus*
  in Tasmania, year 2001. HTTP 200 returned total count 17 with zero
  occurrence rows and empty `facetResults`. The requested `facet=false` is
  operator-reported and is not echoed by the retained raw body. No 2002/2003
  selector was needed.
- The official OpenAPI contract and pinned source commit were recorded. The
  documented architecture directs larger queries to offline download, while
  search has a 5,000-result depth cap and the source default offline maximum
  is 100,000,000 (OccurrenceController.java lines 874-900 and
  DownloadService.java lines 232-239 at the pinned commit). Production
  operability is `unverified_http_403`; deployed offline maximum is unknown.
- Exactly one operator-reported GET submission attempt was made with
  runtime-only email and the frozen projection/quality/privacy controls. It
  returned HTTP 403 before a job/status handle was retained. No causal
  attribution is made. No retry, POST, alternate host, auth/JWT/API key,
  polling, cancellation, archive, or occurrence rows occurred. The sanitized
  request ledger is not independently reconstructible because raw request,
  response body, headers, and handle were not retained.
- Tracked evidence is under
  `evidence/ala_offline_download/2026-07-24/`; raw count material is under the
  ignored authorized directory. No stage, commit, or push performed.

## State

`blocked_submission_http_403_no_job_handle_observed`; architecture is
documented separately from unverified production operability.
