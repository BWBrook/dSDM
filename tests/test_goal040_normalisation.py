from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

import dsdm_phase1.goal040_normalisation as normalisation
from dsdm_phase1.goal040_taxonomy import ANCHORS


def test_half_open_cell_arithmetic_and_qc_precedence():
    assert normalisation._cell_indices("135.370", "-43.6325") == (0, 0)
    assert normalisation._cell_indices("135.380", "-43.6225") == (1, 1)
    assert normalisation._cell_indices("135.369999", "-43.6325") is None
    absent = {"occurrenceStatus": "ABSENT", "basisOfRecord": "FOSSIL_SPECIMEN"}
    assert normalisation._classify_qc(absent)[0] == "occurrence_status_absent"
    fossil = {"occurrenceStatus": "PRESENT", "basisOfRecord": "FOSSIL_SPECIMEN"}
    assert normalisation._classify_qc(fossil)[0] == "fossil_or_subfossil"
    retained = {
        "occurrenceStatus": "PRESENT", "year": "2005", "eventDate": "2005-02-03",
        "decimalLongitude": "135.375", "decimalLatitude": "-43.6275",
        "COORDINATE_INVALID": "true",
    }
    reason, flags, cell = normalisation._classify_qc(retained)
    assert reason is None and cell == (0, 0)
    assert set(flags) == {"COORDINATE_INVALID", "uncertainty_missing"}
    assert normalisation._classify_qc({"occurrenceStatus": ""})[0] == "occurrence_status_unrecognised_or_blank"
    malformed = dict(retained, eventDate="not-a-date")
    reason, flags, cell = normalisation._classify_qc(malformed)
    assert reason is None and cell == (0, 0) and "event_date_unparseable" in flags
    assert normalisation._classify_qc(dict(retained, eventDate="2006-02-03"))[0] == "event_date_year_conflict"


def test_identity_requires_exact_reviewed_value_and_conflicts_fail_closed():
    identities = {"Taxon alpha": "Taxon alpha", "concept-a": "Taxon alpha", "concept-b": "Taxon beta"}
    assert normalisation._attributed_species({"scientificName": "Taxon alpha subsp."}, identities) is None
    assert normalisation._attributed_species({"scientificName": "Taxon alpha", "taxonConceptID": "concept-a"}, identities) == "Taxon alpha"
    with pytest.raises(normalisation.Goal040NormalisationError, match="cross_taxon"):
        normalisation._attributed_species({"scientificName": "Taxon alpha", "taxonConceptID": "concept-b"}, identities)


def test_canonical_cell_ledger_and_same_taxon_duplicate_payload_are_fail_closed(tmp_path):
    path = tmp_path / normalisation.CELL_PATH
    path.parent.mkdir(parents=True)
    path.write_text("canonical\n")
    boundary = {"exact_study_domain": {"grid": {"ignored_cell_ledger_sha256": normalisation._sha(path)}}}
    assert normalisation._validate_cell_ledger(tmp_path, boundary) == path
    path.write_text("tampered\n")
    with pytest.raises(normalisation.Goal040NormalisationError, match="authority_drift"):
        normalisation._validate_cell_ledger(tmp_path, boundary)

    connection = normalisation._open_db(tmp_path / "duplicates.sqlite")
    try:
        first = {"occurrenceStatus": "PRESENT", "year": "2005"}
        fingerprint = normalisation._qa_payload_fingerprint(first)
        assert normalisation._duplicate_record(connection, "record", "Taxon alpha", fingerprint) is False
        assert normalisation._duplicate_record(connection, "record", "Taxon alpha", fingerprint) is True
        with pytest.raises(normalisation.Goal040NormalisationError, match="same_taxon_payload_conflict"):
            normalisation._duplicate_record(connection, "record", "Taxon alpha", normalisation._qa_payload_fingerprint(dict(first, year="2006")))
    finally:
        connection.close()


def test_private_materialisation_receipt_rejects_tampered_species_cells(tmp_path):
    output = tmp_path / normalisation.OUTPUT_ROOT
    output.mkdir(parents=True)
    audit_row = ["record", "Taxon alpha", "Taxon alpha", "accepted_presence", "", "cell"]
    with (output / "row_audit.csv").open("w", newline="") as handle:
        writer = csv.writer(handle); writer.writerow(normalisation.AUDIT_FIELDS); writer.writerow(audit_row)
    species_row = ["Taxon alpha", "cell", "1", "southeast_mainland"]
    with (output / "species_cells.csv").open("w", newline="") as handle:
        writer = csv.writer(handle); writer.writerow(normalisation.SPECIES_CELL_FIELDS); writer.writerow(species_row)
    census = {field: {"value": 1} for field in normalisation.CENSUS_FIELDS}
    (output / "qa_value_frequency_census.json").write_text(json.dumps(census), encoding="utf-8")
    result = {
        "input_rows": 1, "species_cell_rows": 1,
        "row_audit_content_sha256": hashlib.sha256(normalisation._canonical(audit_row)).hexdigest(),
        "species_cell_sha256": hashlib.sha256(("\t".join(species_row) + "\n").encode()).hexdigest(),
        "qa_value_frequency_census_sha256": hashlib.sha256(normalisation._canonical(census)).hexdigest(),
    }
    assert normalisation._private_materialisation(tmp_path, result)["species_cells"]["rows"] == 1
    with (output / "species_cells.csv").open("a", encoding="utf-8") as handle:
        handle.write("tamper\n")
    with pytest.raises(normalisation.Goal040NormalisationError, match="row_schema_drift"):
        normalisation._private_materialisation(tmp_path, result)


def _write_row(writer: csv.DictWriter, record_id: str, species: str, column: int) -> None:
    writer.writerow({
        "recordID": record_id, "taxonConceptID": f"concept-{species}",
        "scientificName": species, "occurrenceStatus": "PRESENT", "year": "2005",
        "eventDate": "2005-02-03", "decimalLongitude": str(135.375 + column * 0.01),
        "decimalLatitude": "-43.6275", "coordinateUncertaintyInMeters": "20",
    })


def test_streamed_rows_deduplicate_and_apply_frozen_shared_rule(tmp_path, monkeypatch):
    taxa = sorted(ANCHORS) + [f"Taxon {index:02d}" for index in range(16)]
    (tmp_path / "metadata").mkdir()
    (tmp_path / "config").mkdir()
    (tmp_path / normalisation.CONTRACT_PATH).write_text(json.dumps({
        "goal_id": "goal040-se-mammal-acquisition-feasibility",
        "time": {"start_year": 2001, "end_year": 2025, "inclusive": True},
        "acquisition": {"qa": {"provider_record_deduplication_key": "recordID_required", "valid_coordinates_required": True, "reported_uncertainty_exclusion_threshold_m": 1000, "missing_uncertainty_action": "retain_flagged_unknown", "no_nearest_land_rescue": True, "collapse_to_one_presence_per_species_cell": True}},
        "data_sufficiency_tiers": {"support_observed": {"minimum_distinct_post_qc_cells_any_region": 1}, "mainland_pretraining_candidate": {"minimum_distinct_post_qc_mainland_cells": 100}, "shared_evaluation_candidate": {"minimum_distinct_post_qc_mainland_cells": 100, "minimum_distinct_post_qc_tasmania_cells": 30}},
    }))
    fieldnames = ["scientific_name", "query_roles", "query_concepts", "accepted_descendants", "shared_evaluation_eligible"]
    with (tmp_path / normalisation.LEDGER_PATH).open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames); writer.writeheader()
        for taxon in taxa:
            writer.writerow({"scientific_name": taxon, "query_roles": "mainland_donor_pretraining", "query_concepts": json.dumps([f"concept-{taxon}"]), "accepted_descendants": "[]", "shared_evaluation_eligible": str(taxon in ANCHORS).lower()})
    (tmp_path / normalisation.DOMAIN_PATH).write_text(json.dumps({"exact_study_domain": {}}))
    plan = {"queries": [], "total": 0}
    header = ["recordID", "taxonConceptID", "scientificName", "occurrenceStatus", "year", "eventDate", "decimalLongitude", "decimalLatitude", "coordinateUncertaintyInMeters"]
    for taxon in taxa:
        query = {"taxon": taxon, "branch_id": taxon.replace(" ", "_").lower() + "__taxon_union", "expected_rows": 1}
        plan["queries"].append(query)
        _, path, _ = normalisation._paths(tmp_path, query["branch_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=header); writer.writeheader()
            if taxon in ANCHORS:
                for column in range(130):
                    _write_row(writer, f"{taxon}-{column}", taxon, column)
                query["expected_rows"] = 130
            else:
                _write_row(writer, taxon, taxon, 0)
        plan["total"] += query["expected_rows"]

    def cells(connection, _path):
        connection.executemany("INSERT INTO cells VALUES (?, ?, ?, ?, ?)", [
            (0, column, f"c{column}", "1", "southeast_mainland") for column in range(100)
        ] + [
            (0, column, f"c{column}", "6", "tasmania") for column in range(100, 130)
        ])

    monkeypatch.setattr(normalisation, "validate_taxon_freeze", lambda _root: {})
    monkeypatch.setattr(normalisation, "validate_acquisition", lambda _root, **_kwargs: {"rows": plan["total"]})
    monkeypatch.setattr(normalisation, "validate_domain_manifest", lambda _domain: None)
    monkeypatch.setattr(normalisation, "_validate_cell_ledger", lambda _root, _boundary: tmp_path / "unused.csv")
    monkeypatch.setattr(normalisation, "_load_cells", cells)
    result = normalisation._normalise(tmp_path, write_outputs=False, plan_loader=lambda _root: plan)
    assert result["input_rows"] == plan["total"]
    assert result["dispositions"] == {"accepted_presence": plan["total"]}
    assert all(result["tiers"][taxon]["shared_evaluation_candidate"] for taxon in ANCHORS)
    assert not result["tiers"]["Taxon 00"]["shared_evaluation_candidate"]
