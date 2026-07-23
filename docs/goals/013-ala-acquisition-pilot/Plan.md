# Plan: Goal 013 ALA Acquisition Pilot

1. Verify the exact clean Goal 012 publication baseline and read its packet,
   frozen request profile, evidence, module, and focused tests.
2. Freeze a declarative 23-request pilot plan with a 575-row hard ceiling,
   `occurrenceID` ascending pagination, and exact Goal 012 filters and fields.
3. Add tests first for plan/profile drift, cap enforcement, response and
   identifier validation, stable pagination, raw/evidence checksums, evidence
   leakage, semantic tampering, and false readiness.
4. Implement the smallest reusable direct-API acquisition and replay surface,
   then execute the live requests sequentially into the ignored raw directory.
5. Build sanitized request and review evidence from raw reconstruction,
   perform one focused repair pass if material defects appear, and run the
   full validation ladder.

`occurrenceID asc` is a bounded pilot order, not a claim of
snapshot-consistent pagination. The final review must preserve the
occurrence-search route's 5,000-result ceiling and the need for a later
supported download/export design above that ceiling.

## Stop rules

Stop on baseline drift, inability to enforce the request or row ceiling,
authentication or bulk workflow, unsupported/ambiguous pagination, schema
behaviour that invalidates the frozen fields, any write outside the authorized
paths, or any risk of tracking occurrence or coordinate payload values.
