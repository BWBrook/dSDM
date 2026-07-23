# Log: Goal 012 ALA Query-Scope Preflight

## 2026-07-23 - Start checkpoint

- Working directory: `/Users/bwbrook/papers/dSDM`.
- Branch: `main`; HEAD and `origin/main`:
  `831bcf7cde40b2623087fbda7ecd7ce4b4a80b7c`.
- Status: `## main...origin/main`.
- No repo-local `AGENTS.md` in this repository.
- Goal 012 packet created and read in Goal -> Plan -> Runbook -> Log order.
- No implementation, occurrence payload, private source, staging, commit, or
  push performed at this checkpoint.

## 2026-07-23 - Live count-only preflight

- The official OpenAPI document is `https://docs.ala.org.au/openapi/specs/biocache.json` (Occurrence REST services, version 3.0). Its server base plus
  `/occurrences/search` is the supported public route:
  `https://api.ala.org.au/occurrences/occurrences/search`.
- The request profile freezes `GET`, `q` taxon/name syntax, `stateProvince:Tasmania`,
  inclusive `year:[2001 TO 2025]`, `pageSize=0`, `facet=false`, and
  `disableAllQualityFilters=true`; local explicit quality rules remain the
  future normalization gate. BIE metadata confirms the Macropus synonym's
  accepted parent and the three Vombatus child concepts.
- Twenty-four count-only probes were retained with HTTP 200, empty
  `occurrences`, and no coordinates or record rows: nine parent probes,
  synonym-ID/name probes, three Tasmania child probes, four Tasmania
  intersections, and six national Vombatus direct/intersection controls.
- Tasmania parent counts (ordered focal species): 4525, 3191, 398, 1615,
  367, 2391, 33442, 1169, 3736. Macropus normalized-name count/intersection
  is 398/398; synonym-ID is 0. Vombatus Tasmania child pairs are 0/0,
  1312/1312, and 644/644; national controls are 550/550, 3302/3302, and
  868/868. Positive intersections establish containment; zero Tasmania
  hirsutus remains an acquisition-time assertion rather than an ecological
  result.
- Decision: parent-species expansion is the default runtime query mode,
  supported by positive national controls, positive Tasmania controls, and
  Macropus name normalization. Retain explicit parent + required synonym +
  all three children as the mandatory fallback, deduplicated by `occurrenceID`.
- No occurrence rows, coordinates, camera/private data, or bulk exports were
  retained. Later acquisition is operationally ready apart from P1-D008 and
  the stated acquisition-time coverage assertions.

## 2026-07-23 - Focused repair

- Rebound all 24 stored probes to one immutable canonical matrix: current
  double-route endpoint, GET, HTTP 200, exact ordered request parameters,
  scope, URL, and semantically checked response query echo. Every response
  remains pageSize=0, facet=false, empty `occurrences`, and empty
  `facetResults`.
- Replaced facet-based containment with direct descendant versus
  parent-filtered intersection counts. The Tasmania hirsutus 0/0 relation is
  resolved only via its positive national 550/550 control; overall unresolved
  is false, while hirsutus and synonym-ID zero coverage remain acquisition-time
  assertions. Explicit parent+alias+child occurrenceID-deduplicated fallback
  remains mandatory.
- Added HTTP-200 metadata-only index-field evidence for all 20 required ALA
  fields, structured project-field derivation/null rules, exact future `fl`
  set, retrieval/profile/request/checksum provenance, and pinned biocache
  lft/rgt implementation commit/source URLs. No bulk acquisition was run.

## 2026-07-23 - Final integrity cleanup

- No new live occurrence count probes or payloads were requested. The existing
  metadata snapshot remains `2026-07-23T12:46:13Z` (including the official
  OpenAPI `fl` parameter and index-field flags); the review was reissued at
  `2026-07-23T12:50:00Z`, after the probe snapshot (`12:27:13Z`) and metadata,
  with `scope_snapshot` equal to the probe timestamp.
- Replay now requires ISO-8601-Z chronology, exact q/fq/quality semantics,
  optional echo controls pageSize=0/start=0/facet=false, OpenAPI parameter
  metadata including `fl`, indexed/stored=true for every mapped field, and an
  exact mapping-field union equal to the frozen future `fl` set.
- Removed the legacy bulk-readiness claim. The retained state is explicitly
  `bulk_execution=false` and `preflight_complete_ready_for_bounded_acquisition_design_execution`,
  with the bounded readiness caveat and P1-D008 prerequisite validated.
