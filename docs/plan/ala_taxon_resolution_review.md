# Goal 010 ALA taxon-resolution review

Evidence package: `evidence/ala_taxon_resolution/2026-07-23/`
Retrieved: 2026-07-23 (UTC timestamp recorded in `manifest.json`)
Bundle: `dsdm-phase1-decision-bundle` (the authoritative nine-species bundle)

This is an evidence gate for later review. “Recommendable” means that the
stored official responses pass the exact-name, rank, classification, concept
ID, round-trip, and BIE accepted-concept checks. It does not approve a taxon
mapping, alter P1-D003, or authorise occurrence acquisition.

## Candidate review

| species_id | returned scientific name | authorship | selected ALA concept ID | match | issues | raw synonym count | evidence-backed alias | recommendation |
|---|---|---|---|---|---|---:|---|---|
| `thylogale_billardierii` | *Thylogale billardierii* | (Desmarest, 1822) | `https://biodiversity.org.au/afd/taxa/82e69509-af63-4502-86f7-43362b777865` | `exactMatch` | `noIssue` | 4 | — | recommendable |
| `notamacropus_rufogriseus` | *Notamacropus rufogriseus* | (Desmarest, 1817) | `https://biodiversity.org.au/afd/taxa/c4dfafef-5192-4a3d-815c-040c393e9bca` | `exactMatch` | `noIssue` | 4 | *Macropus rufogriseus* | recommendable |
| `macropus_giganteus` | *Macropus giganteus* | Shaw, 1790 | `https://biodiversity.org.au/afd/taxa/f2f43ef9-89fd-4f89-8b06-0842e86cfe06` | `exactMatch` | `noIssue` | 9 | — | recommendable |
| `trichosurus_vulpecula` | *Trichosurus vulpecula* | (Kerr, 1792) | `https://biodiversity.org.au/afd/taxa/ee2cb6a9-e17c-4ca7-8aef-76d69eb969ed` | `exactMatch` | `noIssue` | 0 | — | recommendable |
| `pseudocheirus_peregrinus` | *Pseudocheirus peregrinus* | (Boddaert, 1785) | `https://biodiversity.org.au/afd/taxa/003decd6-ec3d-468e-909d-da396a6dd1f6` | `exactMatch` | `noIssue` | 0 | — | recommendable |
| `vombatus_ursinus` | *Vombatus ursinus* | (Shaw, 1800) | `https://biodiversity.org.au/afd/taxa/66d42847-c556-4fa3-902c-a91d9f517286` | `exactMatch` | `noIssue` | 1 | — | recommendable |
| `sarcophilus_harrisii` | *Sarcophilus harrisii* | (Boitard, 1841) | `https://biodiversity.org.au/afd/taxa/c6b5ff5a-a991-4972-b5b0-4214141d5bd6` | `exactMatch` | `noIssue` | 4 | — | recommendable |
| `dasyurus_maculatus` | *Dasyurus maculatus* | (Kerr, 1792) | `https://biodiversity.org.au/afd/taxa/73c23669-c491-42d0-83b3-6fd84a03689a` | `exactMatch` | `noIssue` | 2 | — | recommendable |
| `dasyurus_viverrinus` | *Dasyurus viverrinus* | (Shaw, 1800) | `https://biodiversity.org.au/afd/taxa/1e9f1b49-78b5-409d-91f2-21615ce88e9d` | `exactMatch` | `noIssue` | 6 | — | recommendable |

The raw BIE synonym arrays are retained in `candidates.json`; the table lists
only the one alias promoted as evidence-backed. The `Macropus rufogriseus`
alias is supported by a separate BIE GUID response whose accepted identifier
is the selected *Notamacropus* concept. Other raw synonym strings, spelling
variants, and infraspecific names remain unpromoted.

## Official surfaces and retrieval record

- ALA Name Matching OpenAPI source: `https://docs.ala.org.au/openapi/specs/namematching.json`
- Exact classification: `namematching-ws.ala.org.au/api/searchByClassification`
  with the canonical scientific name plus `kingdom=Animalia`, `class=Mammalia`,
  and `rank=species`.
- Concept round-trip: `namematching-ws.ala.org.au/api/getByTaxonID`.
- BIE name resolution and metadata: `bie-ws.ala.org.au/ws/guid/{name}` and
  `bie-ws.ala.org.au/ws/species/{taxon-concept-id}`.

The package contains one OpenAPI snapshot and five response snapshots per
species (classification, simple search, concept round-trip, BIE GUID, and BIE
species detail), plus the alias response. `manifest.json` records URLs,
statuses, content types, relative paths, and SHA-256 checksums. Validation is
stdlib-only and reads these stored responses offline.

## Review boundary

All nine candidates pass the mechanical gate and are therefore recommendable
for human review. This remains a recommendation surface only: no authoritative
bundle, decision register, source contract, occurrence payload, or P1-D003
decision was changed.
