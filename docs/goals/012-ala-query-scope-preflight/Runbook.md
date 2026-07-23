# Runbook: Goal 012 ALA Query-Scope Preflight

## Preconditions

Run from `/Users/bwbrook/papers/dSDM`; confirm branch `main`, HEAD and
`origin/main` at `831bcf7cde40b2623087fbda7ecd7ce4b4a80b7c`, and clean status.
Read `Goal.md`, `Plan.md`, `Runbook.md`, and `Log.md` in that order.

## Required validation

```sh
python3 tests/test_ala_query_scope.py
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m json.tool config/ala_acquisition_request_profile.json >/dev/null
python3 -m py_compile src/dsdm_phase1/*.py tests/test_ala_query_scope.py
git diff --check
```

Validate the evidence checksum manifest and offline replay. Confirm every
retained response is record-free and that the changed/forbidden-path audit is
empty outside the Goal 012 packet, profile, module, tests, and evidence.

The evidence package must contain 24 probes: nine Tasmania/year parent probes,
the Macropus synonym-ID and normalized-name probes, three Tasmania/year child
probes, four Tasmania/year parent intersections, and six national Vombatus
direct/intersection controls. The expected replay result is parent-species
expansion as default with explicit union fallback.

Replay must validate each stored endpoint, method, HTTP status, ordered request
parameters, canonical URL, scope, and response `q`/`fq`/quality echo. Pagination
controls may be omitted from an echo, but `facet=false` and empty
`facetResults` are mandatory. Metadata replay also checks the OpenAPI route,
BIE concept mapping, metadata-only index-field evidence, and pinned biocache
lft/rgt implementation source.

The metadata parameter subset must include the official `fl` definition. Each
retained available field must be indexed and stored, and its union with the
structured mapping must equal the frozen future retrieval set. Review
timestamps must be valid ISO-Z and later than the probe and metadata snapshots;
the legacy bulk-readiness claim is forbidden.

No occurrence rows, coordinates, camera/private data, staging, commit, push,
or live payload retention are permitted.
