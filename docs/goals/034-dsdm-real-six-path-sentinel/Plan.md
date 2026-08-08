# Plan

1. Freeze Goal027/028/031/033 authorities, the Goal033 `resmlp13` winner, the
   sentinel case, six methods, lifecycle, privacy boundary, and exact fit
   arithmetic in one strict configuration.
2. Export the real outer-training-only bundle locally. Preserve exact
   `build_ladders` membership and ordering, serialize only float32 matrices,
   int32 species indices, aggregate metadata, and digests, then discard local
   row identities.
3. Run a production-shaped bounded sentinel twice on Mac CPU and twice on the
   same Alien GPU/runtime. Reuse only the three permitted auxiliary artifacts;
   rebuild every target model per method and endpoint.
   Both routes must use the configured shared runtime and source fingerprint.
4. Validate each same-route repeat and compare aggregate timings, especially
   pooled and multihead pretraining plus the frozen/full target paths. Choose
   the route that minimizes reliable wall time with acceptable operational
   burden.
5. Record the route and a later full-run handoff. Stop before building or
   launching that full queue and before any ecological scoring.

The later lifecycle remains 8,400 target plus 440 auxiliary logical artifacts
(8,840 total). It is explicitly outside Goal034.
