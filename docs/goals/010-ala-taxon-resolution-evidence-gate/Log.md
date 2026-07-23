# Log: Goal 010 ALA Taxon Resolution Evidence Gate

## 2026-07-23 - Start checkpoint

- Working directory: `/Users/bwbrook/papers/dSDM`.
- Branch: `main`.
- HEAD: `f61846ec08ad254d14b5f38ad21f1b9626ee4939`.
- Status: `## main...origin/main`.
- Repo-local `AGENTS.md`: absent.
- No unrelated dirty files were present before this packet.

## 2026-07-23 - Read set

- Read Goal 008/009 packets, authoritative bundle, contracts, manifests,
  exports, tests, and compact synthetic planning surfaces.
- No `data/`, `temp/`, occurrence payloads, or camera material were read.

## 2026-07-23 - Implementation checkpoints

- Added a stdlib-only retriever/validator in
  `src/dsdm_phase1/ala_taxon_resolution.py` and a bounded runner at
  `scripts/retrieve_ala_taxon_resolution.py`.
- The live retrieval wrote the compact package under
  `evidence/ala_taxon_resolution/2026-07-23/`: one Name Matching OpenAPI
  snapshot, five response snapshots for each of nine species, and one
  evidence-backed alias response. The manifest records URLs, statuses,
  content types, relative paths, and SHA-256 checksums.
- The exact gate returned 9/9 `recommendable` candidates. The only promoted
  alias is `Macropus rufogriseus` for the accepted
  `Notamacropus rufogriseus` concept; all other raw BIE synonym strings remain
  unpromoted.
- Added six offline mutation tests covering fuzzy match, rank/classification,
  duplicate concept, missing/checksum response, and invented alias failures.
- Added the nine-row review table at
  `docs/plan/ala_taxon_resolution_review.md`.
- Validation is offline after retrieval and does not open `data/`, `temp/`,
  occurrence payloads, or camera material.
- Verification: the Goal 010 module tests pass 6/6; the full repository suite
  passes 52/52; JSON parse, direct test execution, Python compilation, and
  `git diff --check` all pass.
- P1-D003 remains pending; this goal cannot update the authoritative bundle or
  decision register.

## 2026-07-23 - Focused raw-evidence linkage repair

- Strengthened `validate_evidence_package` to rebuild every candidate from the
  stored classification, simple-search, taxon-ID round-trip, BIE GUID, BIE
  species, and alias responses, then require exact contract equality.
- Added independent expected-family checks, HTTPS AFD UUID checks, canonical
  identity/species-ID agreement, accepted BIE concept and classification
  checks, exact request URL/method/status/content-type checks, UTC timestamp
  checks, official-surface identity checks, OpenAPI endpoint presence checks,
  and package-relative path checks.
- Added focused mutation-test coverage across 10 mutation families (11 Goal010
  tests total) covering
  forged candidate fields/concept, simple/speciesID/round-trip disagreement,
  BIE GUID and accepted-detail mutations, manifest status/URL/query/OpenAPI,
  alias relabelling, and unsafe paths, while preserving the original
  checksum/missing/fuzzy/rank/duplicate/invented-alias tests.
- Raw snapshots were not edited or re-retrieved. All 47 stored raw response
  files (OpenAPI, 45 species responses, and one alias response) exist and
  match their manifest SHA-256 checksums.
- Focused tests: 11/11; full repository suite after repair: 57/57.
