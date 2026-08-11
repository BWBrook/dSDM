"""Offline streaming QC and species-cell normalisation for Goal 040."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sqlite3
import tempfile
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from pathlib import Path
from typing import Any, Callable

from .goal040_acquisition import _load_plan, _paths, validate_acquisition
from .goal040_domain import validate_domain_manifest
from .goal040_taxonomy import ANCHORS, validate_taxon_freeze


MANIFEST_PATH = Path("metadata/goal040_normalisation_manifest.json")
OUTPUT_ROOT = Path("data/raw/goal040/normalisation")
LEDGER_PATH = Path("metadata/goal040_taxon_query_ledger.csv")
DOMAIN_PATH = Path("metadata/goal040_domain_boundary_manifest.json")
ACQUISITION_PATH = Path("metadata/goal040_acquisition_manifest.json")
CELL_PATH = Path("data/raw/goal040/domain/eligible_cells.csv")
CONTRACT_PATH = Path("config/goal040_se_mammal_feasibility.json")
GRID_ORIGIN_LON = Decimal("135.375")
GRID_ORIGIN_LAT = Decimal("-43.6275")
GRID_STEP = Decimal("0.01")
GRID_HALF_STEP = Decimal("0.005")
GRID_COLUMNS, GRID_ROWS = 1826, 1986
# These are the only exact exclusion values present in the private census for
# this frozen acquisition. Empty categories deliberately do not use text rules.
FOSSIL_BASIS = {"FOSSIL_SPECIMEN"}
CAPTIVE_BASIS: set[str] = set()
INTRODUCED_MEANS: set[str] = set()
CAPTIVE_MEANS: set[str] = set()
ASSERTION_FIELDS = ("COORDINATE_INVALID", "temporalIssue", "taxonomicIssue")
AUDIT_FIELDS = ["record_id", "query_taxon", "attributed_species", "disposition", "diagnostic_flags", "cell_id"]
SPECIES_CELL_FIELDS = ["species", "cell_id", "state_code", "region"]
CENSUS_FIELDS = ("occurrenceStatus", "basisOfRecord", "establishmentMeans")
PRIVATE_OUTPUTS = ("qa_value_frequency_census.json", "row_audit.csv", "species_cells.csv")


class Goal040NormalisationError(ValueError):
    """Fail-closed normalisation error without private occurrence values."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise Goal040NormalisationError(reason)


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean_record_id(value: str | None) -> bool:
    return bool(value and value.strip()) and not any(ord(char) < 32 or ord(char) == 127 for char in value)


def _truth(value: str | None) -> bool:
    return (value or "").strip().lower() == "true"


def _decimal(value: str | None) -> Decimal | None:
    try:
        result = Decimal((value or "").strip())
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def _cell_indices(longitude: str | None, latitude: str | None) -> tuple[int, int] | None:
    lon, lat = _decimal(longitude), _decimal(latitude)
    if lon is None or lat is None or not (-180 <= lon <= 180 and -90 <= lat <= 90):
        return None
    column = int(((lon - GRID_ORIGIN_LON + GRID_HALF_STEP) / GRID_STEP).to_integral_value(rounding=ROUND_FLOOR))
    row = int(((lat - GRID_ORIGIN_LAT + GRID_HALF_STEP) / GRID_STEP).to_integral_value(rounding=ROUND_FLOOR))
    if not (0 <= column < GRID_COLUMNS and 0 <= row < GRID_ROWS):
        return None
    return row, column


def _event_year(value: str | None) -> int | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        year = int(text)
    except ValueError:
        return None
    return year if 1000 <= year <= 9999 and text == str(year) else None


def _date_year(value: str | None) -> int | None:
    text = (value or "").strip()
    if not text:
        return None
    if len(text) < 10 or text[4:5] != "-" or text[7:8] != "-":
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.year


def _qa_payload_fingerprint(row: dict[str, str]) -> str:
    fields = (
        "occurrenceStatus", "basisOfRecord", "establishmentMeans", "year", "eventDate",
        "decimalLatitude", "decimalLongitude", "coordinateUncertaintyInMeters", *ASSERTION_FIELDS,
    )
    return hashlib.sha256(_canonical({field: (row.get(field) or "").strip() for field in fields})).hexdigest()


def _validate_cell_ledger(root: Path, boundary: dict[str, Any]) -> Path:
    path = root / CELL_PATH
    expected = boundary.get("exact_study_domain", {}).get("grid", {}).get("ignored_cell_ledger_sha256")
    _require(isinstance(expected, str) and len(expected) == 64, "eligible_cell_ledger_authority_missing")
    _require(path.is_file() and _sha(path) == expected, "eligible_cell_ledger_authority_drift")
    return path


def _identity_authority(root: Path) -> tuple[dict[str, str], dict[str, set[str]]]:
    with (root / LEDGER_PATH).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    identities: dict[str, str] = {}
    expected: dict[str, set[str]] = {}
    for row in rows:
        species = row["scientific_name"]
        roles = row["query_roles"]
        if not roles:
            continue
        concepts = json.loads(row["query_concepts"])
        descendants = json.loads(row["accepted_descendants"])
        names = {species, *(item["name"] for item in descendants)}
        values = {str(value) for value in concepts} | names
        expected[species] = values
        for value in values:
            prior = identities.get(value)
            _require(prior in (None, species), "identity_authority_cross_taxon_conflict")
            identities[value] = species
    _require(len(expected) == 21, "identity_authority_taxon_coverage_drift")
    return identities, expected


def _validate_contract(root: Path) -> None:
    try:
        contract = json.loads((root / CONTRACT_PATH).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Goal040NormalisationError("normalisation_contract_invalid") from exc
    _require(contract.get("goal_id") == "goal040-se-mammal-acquisition-feasibility", "normalisation_contract_goal_drift")
    _require(contract.get("time") == {"start_year": 2001, "end_year": 2025, "inclusive": True}, "normalisation_contract_time_drift")
    qa = contract.get("acquisition", {}).get("qa", {})
    _require(qa.get("provider_record_deduplication_key") == "recordID_required" and qa.get("valid_coordinates_required") is True and qa.get("reported_uncertainty_exclusion_threshold_m") == 1000 and qa.get("missing_uncertainty_action") == "retain_flagged_unknown" and qa.get("no_nearest_land_rescue") is True and qa.get("collapse_to_one_presence_per_species_cell") is True, "normalisation_contract_qa_drift")
    tiers = contract.get("data_sufficiency_tiers", {})
    _require(tiers.get("support_observed", {}).get("minimum_distinct_post_qc_cells_any_region") == 1 and tiers.get("mainland_pretraining_candidate", {}).get("minimum_distinct_post_qc_mainland_cells") == 100 and tiers.get("shared_evaluation_candidate", {}).get("minimum_distinct_post_qc_mainland_cells") == 100 and tiers.get("shared_evaluation_candidate", {}).get("minimum_distinct_post_qc_tasmania_cells") == 30, "normalisation_contract_tier_drift")


def _attributed_species(row: dict[str, str], identities: dict[str, str]) -> str | None:
    hits = {
        identities[value.strip()]
        for field in ("raw_taxonConceptID", "taxonConceptID", "acceptedNameUsageID", "raw_scientificName", "scientificName", "acceptedNameUsage")
        if (value := row.get(field)) and value.strip() in identities
    }
    _require(len(hits) <= 1, "row_identity_cross_taxon_conflict")
    return next(iter(hits), None)


def _classify_qc(row: dict[str, str]) -> tuple[str | None, list[str], tuple[int, int] | None]:
    """Return a single deterministic exclusion, diagnostics, and grid key."""
    flags = [name for name in ASSERTION_FIELDS if _truth(row.get(name))]
    occurrence_status = (row.get("occurrenceStatus") or "").strip()
    if occurrence_status == "ABSENT":
        return "occurrence_status_absent", flags, None
    if occurrence_status != "PRESENT":
        return "occurrence_status_unrecognised_or_blank", flags, None
    if (row.get("basisOfRecord") or "").strip() in FOSSIL_BASIS:
        return "fossil_or_subfossil", flags, None
    if (row.get("basisOfRecord") or "").strip() in CAPTIVE_BASIS or (row.get("establishmentMeans") or "").strip() in CAPTIVE_MEANS:
        return "captive", flags, None
    if (row.get("establishmentMeans") or "").strip() in INTRODUCED_MEANS:
        return "introduced", flags, None
    year, date_year = _event_year(row.get("year")), _date_year(row.get("eventDate"))
    if year is None or not 2001 <= year <= 2025:
        return "temporal_year_invalid_or_outside", flags, None
    if row.get("eventDate", "").strip() and date_year is None:
        flags.append("event_date_unparseable")
    if date_year is not None and date_year != year:
        return "event_date_year_conflict", flags, None
    uncertainty = (row.get("coordinateUncertaintyInMeters") or "").strip()
    if not uncertainty:
        flags.append("uncertainty_missing")
    else:
        reported = _decimal(uncertainty)
        if reported is None or reported < 0 or reported > 1000:
            return "uncertainty_invalid_or_over_1000m", flags, None
    cell = _cell_indices(row.get("decimalLongitude"), row.get("decimalLatitude"))
    if cell is None:
        return "coordinates_invalid_or_outside_grid", flags, None
    return None, flags, cell


def _open_db(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=OFF")
    connection.execute("PRAGMA synchronous=OFF")
    connection.executescript("""
        CREATE TABLE cells (row INTEGER, column_no INTEGER, cell_id TEXT, state TEXT, region TEXT,
          PRIMARY KEY (row, column_no));
        CREATE TABLE identities (record_id TEXT PRIMARY KEY, species TEXT NOT NULL, qa_fingerprint TEXT NOT NULL);
        CREATE TABLE presences (species TEXT, cell_id TEXT, state TEXT, region TEXT,
          PRIMARY KEY (species, cell_id));
    """)
    return connection


def _duplicate_record(connection: sqlite3.Connection, record_id: str, species: str, fingerprint: str) -> bool:
    seen = connection.execute("SELECT species, qa_fingerprint FROM identities WHERE record_id=?", (record_id,)).fetchone()
    if seen is None:
        connection.execute("INSERT INTO identities VALUES (?, ?, ?)", (record_id, species, fingerprint))
        return False
    _require(seen[0] == species, "duplicate_record_id_cross_taxon_conflict")
    _require(seen[1] == fingerprint, "duplicate_record_id_same_taxon_payload_conflict")
    return True


def _load_cells(connection: sqlite3.Connection, path: Path) -> None:
    _require(path.is_file(), "eligible_cell_ledger_missing")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        _require(reader.fieldnames == ["cell_id", "row_south_to_north", "column_west_to_east", "longitude", "latitude", "state_code", "region"], "eligible_cell_ledger_schema_drift")
        connection.executemany(
            "INSERT INTO cells VALUES (?, ?, ?, ?, ?)",
            ((int(row["row_south_to_north"]), int(row["column_west_to_east"]), row["cell_id"], row["state_code"], row["region"]) for row in reader),
        )
    _require(connection.execute("SELECT COUNT(*) FROM cells").fetchone()[0] == 1_125_325, "eligible_cell_ledger_count_drift")


def _audit_writer(path: Path | None) -> tuple[Any, csv.writer | None]:
    if path is None:
        return None, None
    handle = path.open("w", newline="", encoding="utf-8")
    writer = csv.writer(handle, lineterminator="\n")
    writer.writerow(["record_id", "query_taxon", "attributed_species", "disposition", "diagnostic_flags", "cell_id"])
    return handle, writer


def _normalise(root: Path, *, write_outputs: bool, plan_loader: Callable[[Path], dict[str, Any]]) -> dict[str, Any]:
    _validate_contract(root)
    validate_taxon_freeze(root)
    acquisition = validate_acquisition(root, require_raw=True, _plan_loader=plan_loader)
    boundary = json.loads((root / DOMAIN_PATH).read_text(encoding="utf-8"))
    validate_domain_manifest(boundary["exact_study_domain"])
    cell_path = _validate_cell_ledger(root, boundary)
    identities, expected = _identity_authority(root)
    with (root / LEDGER_PATH).open(newline="", encoding="utf-8") as handle:
        shared_eligible = {
            row["scientific_name"]: row["shared_evaluation_eligible"] == "true"
            for row in csv.DictReader(handle) if row["query_roles"]
        }
    plan = plan_loader(root)
    queries = {item["taxon"]: item for item in plan["queries"]}
    _require(set(queries) == set(expected), "normalisation_query_taxon_drift")
    output = root / OUTPUT_ROOT
    if write_outputs:
        if output.exists():
            shutil.rmtree(output)
        output.mkdir(parents=True)
        db_path = output / "normalisation.sqlite"
        audit_path: Path | None = output / "row_audit.csv"
    else:
        temporary = tempfile.TemporaryDirectory(prefix="dsdm-goal040-normalisation-")
        db_path = Path(temporary.name) / "normalisation.sqlite"
        audit_path = None
    connection = _open_db(db_path)
    _load_cells(connection, cell_path)
    rows = Counter()
    dispositions = Counter()
    flags = Counter()
    value_frequencies = {
        field: Counter() for field in CENSUS_FIELDS
    }
    handle, audit = _audit_writer(audit_path)
    audit_content_sha = hashlib.sha256()
    completed = False
    try:
        for taxon, query in sorted(queries.items(), key=lambda item: item[1]["expected_rows"]):
            _, raw_path, _ = _paths(root, query["branch_id"])
            with raw_path.open(newline="", encoding="utf-8-sig") as stream:
                reader = csv.DictReader(stream)
                for row in reader:
                    rows["input"] += 1
                    for field, frequencies in value_frequencies.items():
                        frequencies[(row.get(field) or "").strip()] += 1
                    record_id = row.get("recordID", "")
                    species = _attributed_species(row, identities)
                    disposition: str | None = None
                    row_flags: list[str] = []
                    cell_id = ""
                    if not _clean_record_id(record_id):
                        disposition = "record_id_invalid"
                    elif species is None:
                        disposition = "identity_unresolved"
                    elif species != taxon:
                        raise Goal040NormalisationError("row_identity_does_not_match_query_taxon")
                    else:
                        if _duplicate_record(connection, record_id, species, _qa_payload_fingerprint(row)):
                            disposition = "duplicate_record_id"
                        else:
                            disposition, row_flags, cell = _classify_qc(row)
                            if disposition is None:
                                match = connection.execute("SELECT cell_id, state, region FROM cells WHERE row=? AND column_no=?", cell).fetchone()
                                if match is None:
                                    disposition = "outside_eligible_cell"
                                else:
                                    cell_id, state, region = match
                                    connection.execute("INSERT OR IGNORE INTO presences VALUES (?, ?, ?, ?)", (species, cell_id, state, region))
                                    disposition = "accepted_presence"
                    dispositions[disposition] += 1
                    flags.update(row_flags)
                    audit_content_sha.update(_canonical([record_id, taxon, species or "", disposition, "|".join(sorted(row_flags)), cell_id]))
                    if audit is not None:
                        audit.writerow([record_id, taxon, species or "", disposition, "|".join(sorted(row_flags)), cell_id])
            connection.commit()
        _require(rows["input"] == acquisition["rows"], "normalisation_input_row_reconciliation_drift")
        species_rows = connection.execute("SELECT species, region, COUNT(*) FROM presences GROUP BY species, region").fetchall()
        counts: dict[str, dict[str, int]] = {taxon: {"total": 0, "mainland": 0, "tasmania": 0} for taxon in queries}
        for species, region, total in species_rows:
            counts[species]["total"] += total
            counts[species]["tasmania" if region == "tasmania" else "mainland"] += total
        tiers = {}
        for species in sorted(counts):
            values = counts[species]
            tiers[species] = {
                **values,
                "support_observed": values["total"] >= 1,
                "mainland_pretraining_candidate": values["mainland"] >= 100,
                "shared_evaluation_candidate": shared_eligible[species] and values["mainland"] >= 100 and values["tasmania"] >= 30,
            }
        _require(set(ANCHORS) <= set(tiers), "anchor_coverage_drift")
        species_cell_rows = connection.execute("SELECT species, cell_id, state, region FROM presences ORDER BY species, cell_id").fetchall()
        species_cell_sha = hashlib.sha256()
        for item in species_cell_rows:
            species_cell_sha.update(("\t".join(item) + "\n").encode())
        if write_outputs:
            with (output / "species_cells.csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream, lineterminator="\n")
                writer.writerow(["species", "cell_id", "state_code", "region"])
                writer.writerows(species_cell_rows)
            census = {field: dict(sorted(frequencies.items())) for field, frequencies in value_frequencies.items()}
            census_path = output / "qa_value_frequency_census.json"
            census_path.write_text(json.dumps(census, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        else:
            census = {field: dict(sorted(frequencies.items())) for field, frequencies in value_frequencies.items()}
        result = {
            "input_rows": rows["input"], "identity_rows": connection.execute("SELECT COUNT(*) FROM identities").fetchone()[0],
            "dispositions": dict(sorted(dispositions.items())), "diagnostic_flags": dict(sorted(flags.items())),
            "tiers": tiers, "species_cell_rows": len(species_cell_rows), "species_cell_sha256": species_cell_sha.hexdigest(),
            "qa_value_frequency_census_sha256": hashlib.sha256(_canonical(census)).hexdigest(),
            "row_audit_content_sha256": audit_content_sha.hexdigest(),
        }
        completed = True
    finally:
        if handle is not None:
            handle.close()
        connection.close()
        if write_outputs and completed:
            db_path.unlink()
        if not write_outputs:
            temporary.cleanup()
    _require(sum(result["dispositions"].values()) == result["input_rows"], "row_disposition_reconciliation_drift")
    return result


def _csv_materialisation(
    path: Path, fields: list[str], content_digest: Callable[[list[str]], None],
) -> dict[str, Any]:
    rows = 0
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        _require(header == fields, "private_output_schema_drift")
        for row in reader:
            _require(len(row) == len(fields), "private_output_row_schema_drift")
            content_digest(row)
            rows += 1
    return {
        "bytes": path.stat().st_size, "rows": rows, "sha256": _sha(path),
        "header_sha256": hashlib.sha256(_canonical(fields)).hexdigest(),
    }


def _private_materialisation(root: Path, result: dict[str, Any]) -> dict[str, Any]:
    output = root / OUTPUT_ROOT
    _require(output.is_dir(), "private_output_root_missing")
    _require({path.name for path in output.iterdir()} == set(PRIVATE_OUTPUTS), "private_output_footprint_drift")
    audit_digest = hashlib.sha256()
    audit = _csv_materialisation(
        output / "row_audit.csv", AUDIT_FIELDS,
        lambda row: audit_digest.update(_canonical(row)),
    )
    _require(audit["rows"] == result["input_rows"] and audit_digest.hexdigest() == result["row_audit_content_sha256"], "row_audit_content_drift")
    species_digest = hashlib.sha256()
    species_keys: set[tuple[str, str]] = set()
    def species_content(row: list[str]) -> None:
        key = (row[0], row[1])
        _require(key not in species_keys, "species_cell_duplicate_key")
        species_keys.add(key)
        species_digest.update(("\t".join(row) + "\n").encode())
    species = _csv_materialisation(output / "species_cells.csv", SPECIES_CELL_FIELDS, species_content)
    _require(species["rows"] == result["species_cell_rows"] and species_digest.hexdigest() == result["species_cell_sha256"], "species_cell_content_drift")
    census_path = output / "qa_value_frequency_census.json"
    try:
        census = json.loads(census_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Goal040NormalisationError("qa_value_frequency_census_invalid") from exc
    _require(isinstance(census, dict) and set(census) == set(CENSUS_FIELDS), "qa_value_frequency_census_schema_drift")
    _require(all(isinstance(values, dict) and all(isinstance(count, int) and count >= 0 for count in values.values()) and sum(values.values()) == result["input_rows"] for values in census.values()), "qa_value_frequency_census_count_drift")
    _require(hashlib.sha256(_canonical(census)).hexdigest() == result["qa_value_frequency_census_sha256"], "qa_value_frequency_census_content_drift")
    return {
        "private_footprint": list(PRIVATE_OUTPUTS),
        "row_audit": audit | {"content_sha256": audit_digest.hexdigest()},
        "species_cells": species | {"content_sha256": species_digest.hexdigest()},
        "qa_value_frequency_census": {
            "bytes": census_path.stat().st_size, "rows": result["input_rows"], "sha256": _sha(census_path),
            "schema_sha256": hashlib.sha256(_canonical({"top_level_fields": CENSUS_FIELDS, "value_type": "nonnegative_integer_counts"})).hexdigest(),
            "content_sha256": hashlib.sha256(_canonical(census)).hexdigest(),
        },
    }


def _tracked_manifest(root: Path, result: dict[str, Any], private: dict[str, Any]) -> dict[str, Any]:
    bindings = {
        "contract_sha256": _sha(root / CONTRACT_PATH), "taxon_ledger_sha256": _sha(root / LEDGER_PATH),
        "domain_manifest_sha256": _sha(root / DOMAIN_PATH), "acquisition_manifest_sha256": _sha(root / ACQUISITION_PATH),
        "eligible_cell_ledger_sha256": _sha(root / CELL_PATH),
    }
    summary = {
        "input_rows": result["input_rows"], "identity_rows": result["identity_rows"],
        "accepted_species_cells": result["species_cell_rows"], "dispositions": result["dispositions"],
        "diagnostic_flags": result["diagnostic_flags"],
        "support_observed_taxa": sum(item["support_observed"] for item in result["tiers"].values()),
        "mainland_pretraining_taxa": sum(item["mainland_pretraining_candidate"] for item in result["tiers"].values()),
        "shared_evaluation_taxa": sum(item["shared_evaluation_candidate"] for item in result["tiers"].values()),
    }
    return {
        "schema_version": "1.0", "goal_id": "goal040-se-mammal-acquisition-feasibility", "stage": "qc-species-cell-normalisation",
        "status": "complete_raw_replay_required", "completed_at": _now(), "bindings": bindings,
        "rules": {"cell_assignment": "exact_decimal_half_open_0.01_degree_tiles_joined_to_frozen_eligible_cell_ledger", "record_id": "control_clean_required_global_dedup_after_attribution", "assertions": "diagnostics_only", "uncertainty": "missing_retained_flagged; invalid_or_over_1000m_excluded", "shared_qualification": "frozen_shared_evaluation_eligible_and_100_mainland_and_30_tasmania"},
        "summary": summary, "taxon_tiers": result["tiers"], "anchors_reported": {name: result["tiers"][name] for name in sorted(ANCHORS)},
        "outputs": private,
        "privacy": {"tracked_row_payload": False, "record_ids_retained": False, "coordinates_retained": False, "event_dates_retained": False, "private_paths_retained": False, "donor_cell_associations_retained": False},
    }


def run_normalisation(root: Path, *, _plan_loader: Callable[[Path], dict[str, Any]] = _load_plan) -> dict[str, Any]:
    root = Path(root)
    result = _normalise(root, write_outputs=True, plan_loader=_plan_loader)
    manifest = _tracked_manifest(root, result, _private_materialisation(root, result))
    (root / MANIFEST_PATH).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return validate_normalisation(root, require_raw=True, _plan_loader=_plan_loader)


def validate_normalisation(root: Path, *, require_raw: bool = False, _plan_loader: Callable[[Path], dict[str, Any]] = _load_plan) -> dict[str, Any]:
    root = Path(root)
    _validate_contract(root)
    try:
        manifest = json.loads((root / MANIFEST_PATH).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Goal040NormalisationError("normalisation_manifest_invalid") from exc
    _require(manifest.get("status") == "complete_raw_replay_required" and manifest.get("stage") == "qc-species-cell-normalisation", "normalisation_manifest_identity_drift")
    _require(manifest.get("bindings") == {"contract_sha256": _sha(root / CONTRACT_PATH), "taxon_ledger_sha256": _sha(root / LEDGER_PATH), "domain_manifest_sha256": _sha(root / DOMAIN_PATH), "acquisition_manifest_sha256": _sha(root / ACQUISITION_PATH), "eligible_cell_ledger_sha256": _sha(root / CELL_PATH)}, "normalisation_input_binding_drift")
    text = json.dumps(manifest, sort_keys=True)
    _require(not any(token in text.lower() for token in ("longitude", "latitude", "eventdate", "data/raw/")), "normalisation_manifest_private_material")
    if not require_raw:
        return {"status": "tracked_normalisation_manifest_valid_raw_replay_required", "raw_replay_required": True}
    private = _private_materialisation(root, {
        "input_rows": manifest["summary"]["input_rows"],
        "species_cell_rows": manifest["summary"]["accepted_species_cells"],
        "species_cell_sha256": manifest["outputs"]["species_cells"]["content_sha256"],
        "qa_value_frequency_census_sha256": manifest["outputs"]["qa_value_frequency_census"]["content_sha256"],
        "row_audit_content_sha256": manifest["outputs"]["row_audit"]["content_sha256"],
    })
    replay_result = _normalise(root, write_outputs=False, plan_loader=_plan_loader)
    _require(
        replay_result["species_cell_sha256"] == private["species_cells"]["content_sha256"]
        and replay_result["qa_value_frequency_census_sha256"] == private["qa_value_frequency_census"]["content_sha256"]
        and replay_result["row_audit_content_sha256"] == private["row_audit"]["content_sha256"],
        "normalisation_private_outputs_disagree_with_raw_replay",
    )
    replay = _tracked_manifest(root, replay_result, private)
    for key in ("bindings", "rules", "summary", "taxon_tiers", "anchors_reported", "outputs", "privacy"):
        _require(manifest.get(key) == replay.get(key), "normalisation_raw_replay_disagrees_with_manifest")
    return {"status": "normalisation_complete_raw_replay_validated", "raw_replay_required": False, **manifest["summary"]}
