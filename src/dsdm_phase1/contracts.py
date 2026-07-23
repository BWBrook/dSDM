"""Small validators for Phase 1 synthetic contract fixtures.

These functions enforce scaffold-level rules only. They do not choose species,
ALA filters, camera-trap interpretation, spatial rules, pseudoabsence rules, or
real QA tolerances.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class ValidationError(ValueError):
    """Raised when a Phase 1 contract fixture violates a required rule."""


PHASE1_DECISION_IDS = tuple(f"P1-D{index:03d}" for index in range(1, 31))
PHASE1_SPECIES = (
    ("thylogale_billardierii", "Thylogale billardierii"),
    ("notamacropus_rufogriseus", "Notamacropus rufogriseus"),
    ("macropus_giganteus", "Macropus giganteus"),
    ("trichosurus_vulpecula", "Trichosurus vulpecula"),
    ("pseudocheirus_peregrinus", "Pseudocheirus peregrinus"),
    ("vombatus_ursinus", "Vombatus ursinus"),
    ("sarcophilus_harrisii", "Sarcophilus harrisii"),
    ("dasyurus_maculatus", "Dasyurus maculatus"),
    ("dasyurus_viverrinus", "Dasyurus viverrinus"),
)
PHASE1_ROOT_KEYS = {
    "bundle_id", "schema_version", "decision_register_version", "decisions",
    "species", "policies", "operational_prerequisites", "privacy",
}
PHASE1_POLICY_KEYS = {
    "thylogale_edge_case", "species", "temporal", "ala_resources",
    "ala_quality", "source_versioning", "camera", "source_combination",
    "grid", "boundary", "island_exclusions", "coordinate_assignment",
    "pseudoabsence", "thinning", "spatial_partition", "predictors",
    "categorical_levels", "scaling", "qa", "fixtures", "storage", "tooling",
    "decision_bundle", "legacy_comparison", "initial_scaffold",
}
PHASE1_DECISION_STATUSES = {
    **{decision_id: "resolved" for decision_id in PHASE1_DECISION_IDS},
    "P1-D003": "resolved_with_prerequisite",
    "P1-D008": "resolved_with_prerequisite",
    "P1-D030": "historical_resolved",
}
PHASE1_ACTIVE_PREDICTORS = [
    "annmeantemp", "meandiurnrange", "isothermality", "tempseason",
    "maxtempwarmmonth", "mintempcoldmonth", "tempannrange", "meantempwetq",
    "meantempdryq", "meantempwarmq", "meantempcoldq", "annprecip",
    "precipwetmonth", "precipdrymonth", "precipseason", "precipwetq",
    "precipdryq", "precipwarmq", "precipcoldq", "elevation", "top_roughness",
    "soil_class", "dist_fw", "dist_road", "fpar", "veg_mvg",
    "landuse_secondary", "human_footprint",
]
PHASE1_EXCLUDED_PREDICTORS = [
    "landuse_primary", "landuse_tertiary", "veg_mvs", "fire_freq"
]
PHASE1_ISLAND_CODES = {
    "KI": "King Island", "FI": "Flinders Island", "CBI": "Cape Barren Island",
    "CI": "Clarke Island", "THI": "Three Hummock Island", "HI": "Hunter Island",
    "MI": "Maria Island", "BI": "Bruny Island",
}
PHASE1_ISLAND_MATRIX = {
    "thylogale_billardierii": ["KI", "CBI"],
    "notamacropus_rufogriseus": ["THI", "HI"],
    "macropus_giganteus": ["KI", "FI", "CBI", "CI", "HI", "BI"],
    "trichosurus_vulpecula": ["CBI", "CI", "HI"],
    "pseudocheirus_peregrinus": ["CBI", "CI", "THI", "HI", "BI"],
    "vombatus_ursinus": ["THI", "HI", "BI"],
    "sarcophilus_harrisii": ["KI", "FI", "CBI", "CI", "THI", "HI", "BI"],
    "dasyurus_maculatus": ["KI", "FI", "CBI", "CI", "THI", "HI", "MI", "BI"],
    "dasyurus_viverrinus": ["KI", "FI", "CBI", "CI", "THI", "HI", "MI"],
}


STAGE_REQUIRED_DECISIONS: dict[str, tuple[str, ...]] = {
    "species_contract": ("P1-D001", "P1-D002"),
    "source_contracts": ("P1-D007", "P1-D008", "P1-D009"),
    "mocked_acquisition_requests": (
        "P1-D003",
        "P1-D004",
        "P1-D005",
        "P1-D006",
        "P1-D007",
        "P1-D008",
        "P1-D009",
        "P1-D010",
    ),
}

REQUIRED_SPECIES_FIELDS = (
    "species_id",
    "scientific_name",
    "accepted_name",
    "common_name",
    "class",
    "include_phase1",
    "decision_status",
    "decision_reference",
)

REQUIRED_ROW_PROVENANCE_FIELDS = (
    "run_id",
    "row_id",
    "species_id",
    "scientific_name",
    "source",
    "source_record_id",
    "source_dataset_id",
    "source_dataset_name",
    "pa",
    "pa_type",
    "decision_manifest_id",
    "input_manifest_id",
)

ALLOWED_PA_TYPES = {"presence", "true_absence", "pseudoabsence"}

ALLOWED_SOURCE_TYPES = {"ala_occurrence", "camera_trap"}

REQUIRED_SOURCE_CONTRACT_FIELDS = (
    "source_id",
    "source_type",
    "decision_references",
    "local_path",
    "checksum",
    "license",
    "sensitivity",
    "provenance",
)

SOURCE_TYPE_DECISIONS = {
    "ala_occurrence": ("P1-D007",),
    "camera_trap": ("P1-D008", "P1-D009"),
}

SOURCE_TYPE_REQUIRED_BLOCKS = {
    "ala_occurrence": ("versioning",),
    "camera_trap": ("authority", "true_absence"),
}


def validate_decision_manifest(
    manifest: dict[str, Any], *, stage: str
) -> dict[str, Any]:
    """Validate that all decisions required for a stage are resolved."""

    if stage not in STAGE_REQUIRED_DECISIONS:
        known = ", ".join(sorted(STAGE_REQUIRED_DECISIONS))
        raise ValidationError(f"Unknown stage {stage!r}; known stages: {known}")

    decisions = manifest.get("decisions")
    if not isinstance(decisions, list):
        raise ValidationError("decision manifest requires a decisions list")

    by_id: dict[str, dict[str, Any]] = {}
    for decision in decisions:
        if not isinstance(decision, dict):
            raise ValidationError("each decision must be an object")
        decision_id = decision.get("id")
        if not isinstance(decision_id, str) or not decision_id:
            raise ValidationError("each decision requires a non-empty id")
        by_id[decision_id] = decision

    missing: list[str] = []
    unresolved: list[str] = []
    for decision_id in STAGE_REQUIRED_DECISIONS[stage]:
        decision = by_id.get(decision_id)
        if decision is None:
            missing.append(decision_id)
        elif decision.get("status") != "resolved":
            unresolved.append(decision_id)

    if missing or unresolved:
        details: list[str] = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if unresolved:
            details.append("unresolved: " + ", ".join(unresolved))
        raise ValidationError(
            f"Stage {stage!r} blocked by required decisions; " + "; ".join(details)
        )

    return {
        "stage": stage,
        "required_decisions": list(STAGE_REQUIRED_DECISIONS[stage]),
        "manifest_id": manifest.get("manifest_id"),
    }


def validate_species_contract(contract: dict[str, Any]) -> dict[str, Any]:
    """Validate a synthetic focal-species contract."""

    species = contract.get("species")
    if not isinstance(species, list) or not species:
        raise ValidationError("species contract requires a non-empty species list")

    included_ids: list[str] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(species, start=1):
        if not isinstance(row, dict):
            raise ValidationError(f"species row {index} must be an object")
        missing = [field for field in REQUIRED_SPECIES_FIELDS if field not in row]
        if missing:
            raise ValidationError(
                f"species row {index} missing required fields: {', '.join(missing)}"
            )
        species_id = row["species_id"]
        if not isinstance(species_id, str) or not species_id:
            raise ValidationError(f"species row {index} requires a non-empty species_id")
        if species_id in seen_ids:
            raise ValidationError(f"duplicate species_id: {species_id}")
        seen_ids.add(species_id)
        if row["include_phase1"] is True:
            if row["decision_status"] != "resolved":
                raise ValidationError(
                    f"included species {species_id} has unresolved decision status"
                )
            included_ids.append(species_id)

    return {
        "included_species_ids": included_ids,
        "species_count": len(species),
        "contract_kind": contract.get("fixture_kind"),
    }


def validate_source_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate row-level provenance and presence/absence category separation."""

    if not rows:
        raise ValidationError("source row fixture requires at least one row")

    pa_types: set[str] = set()
    sources_by_pa_type: dict[str, set[str]] = {}

    for index, row in enumerate(rows, start=1):
        missing = [field for field in REQUIRED_ROW_PROVENANCE_FIELDS if field not in row]
        if missing:
            raise ValidationError(
                f"source row {index} missing required fields: {', '.join(missing)}"
            )
        pa_type = row["pa_type"]
        if pa_type not in ALLOWED_PA_TYPES:
            allowed = ", ".join(sorted(ALLOWED_PA_TYPES))
            raise ValidationError(f"source row {index} has invalid pa_type {pa_type!r}; allowed: {allowed}")
        pa = row["pa"]
        if pa_type == "presence" and pa != 1:
            raise ValidationError(f"source row {index} has presence pa_type but pa != 1")
        if pa_type in {"true_absence", "pseudoabsence"} and pa != 0:
            raise ValidationError(f"source row {index} has absence pa_type but pa != 0")
        if pa_type == "true_absence" and not row.get("true_absence_rule_id"):
            raise ValidationError(f"source row {index} true_absence requires true_absence_rule_id")
        if pa_type == "pseudoabsence" and not row.get("pseudoabsence_rule_id"):
            raise ValidationError(f"source row {index} pseudoabsence requires pseudoabsence_rule_id")
        pa_types.add(pa_type)
        sources_by_pa_type.setdefault(pa_type, set()).add(row["source"])

    return {
        "row_count": len(rows),
        "pa_types": sorted(pa_types),
        "sources_by_pa_type": {
            pa_type: sorted(sources)
            for pa_type, sources in sorted(sources_by_pa_type.items())
        },
        "required_provenance_fields": list(REQUIRED_ROW_PROVENANCE_FIELDS),
    }


def validate_manifest_checksums(
    manifest: dict[str, Any], *, base_dir: Path | str
) -> dict[str, Any]:
    """Validate SHA-256 checksums for files listed in a synthetic manifest."""

    base = Path(base_dir).resolve()
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ValidationError("manifest requires a non-empty files list")

    checked: list[str] = []
    for entry in files:
        if not isinstance(entry, dict):
            raise ValidationError("manifest file entries must be objects")
        path_text = entry.get("path")
        expected = entry.get("sha256")
        if not isinstance(path_text, str) or not path_text:
            raise ValidationError("manifest file entry requires path")
        _validate_sha256_hex_digest(
            expected, label=f"manifest file {path_text}"
        )
        _validate_safe_relative_path(path_text, label="manifest file")

        path = (base / path_text).resolve()
        if base != path and base not in path.parents:
            raise ValidationError(f"manifest file path escapes base directory: {path_text}")
        if not path.exists():
            raise ValidationError(f"manifest file does not exist: {path_text}")

        actual = _sha256(path)
        if actual != expected:
            raise ValidationError(
                f"checksum mismatch for {path_text}: expected {expected}, got {actual}"
            )
        checked.append(path_text)

    return {
        "manifest_id": manifest.get("manifest_id"),
        "checked_files": checked,
    }


def validate_source_contracts(bundle: dict[str, Any]) -> dict[str, Any]:
    """Validate synthetic source-contract metadata without reading sources."""

    contracts = bundle.get("contracts")
    if not isinstance(contracts, list) or not contracts:
        raise ValidationError("source-contract bundle requires a non-empty contracts list")

    source_ids: list[str] = []
    source_types: set[str] = set()
    decision_references: set[str] = set()

    for index, contract in enumerate(contracts, start=1):
        if not isinstance(contract, dict):
            raise ValidationError(f"source contract {index} must be an object")
        missing = [
            field
            for field in REQUIRED_SOURCE_CONTRACT_FIELDS
            if field not in contract
        ]
        if missing:
            raise ValidationError(
                f"source contract {index} missing required fields: {', '.join(missing)}"
            )

        source_id = contract["source_id"]
        if not isinstance(source_id, str) or not source_id:
            raise ValidationError(f"source contract {index} requires a non-empty source_id")
        if source_id in source_ids:
            raise ValidationError(f"duplicate source_id: {source_id}")

        source_type = contract["source_type"]
        if source_type not in ALLOWED_SOURCE_TYPES:
            allowed = ", ".join(sorted(ALLOWED_SOURCE_TYPES))
            raise ValidationError(
                f"source contract {source_id} has invalid source_type {source_type!r}; allowed: {allowed}"
            )

        references = contract["decision_references"]
        if not isinstance(references, list) or not references:
            raise ValidationError(f"source contract {source_id} requires decision_references")
        if not all(isinstance(item, str) and item for item in references):
            raise ValidationError(f"source contract {source_id} decision_references must be non-empty strings")
        for decision_id in SOURCE_TYPE_DECISIONS[source_type]:
            if decision_id not in references:
                raise ValidationError(
                    f"source contract {source_id} missing decision reference {decision_id}"
                )

        _validate_safe_relative_path(
            contract["local_path"], label=f"source contract {source_id}"
        )
        _validate_checksum_block(contract["checksum"], label=f"source contract {source_id}")
        _require_non_empty_string(contract, "license", source_id)
        _require_non_empty_string(contract, "sensitivity", source_id)
        _require_non_empty_mapping(contract, "provenance", source_id)
        for block_name in SOURCE_TYPE_REQUIRED_BLOCKS[source_type]:
            block = _require_non_empty_mapping(contract, block_name, source_id)
            expected_decision = {
                "versioning": "P1-D007",
                "authority": "P1-D008",
                "true_absence": "P1-D009",
            }[block_name]
            if block.get("decision_id") != expected_decision:
                raise ValidationError(
                    f"source contract {source_id} {block_name} must reference {expected_decision}"
                )

        source_ids.append(source_id)
        source_types.add(source_type)
        decision_references.update(references)

    return {
        "source_ids": source_ids,
        "source_types": sorted(source_types),
        "decision_references": sorted(decision_references),
        "contract_count": len(contracts),
    }


def load_phase1_decision_bundle(path: Path | str) -> dict[str, Any]:
    """Load and validate the tracked Phase 1 decision bundle only.

    The bundle is a self-contained JSON document. This function intentionally
    does not resolve or open any paths referenced by operational metadata.
    """

    bundle_path = Path(path)
    try:
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot read decision bundle: {bundle_path}") from exc
    if not isinstance(bundle, dict):
        raise ValidationError("decision bundle root must be an object")
    validate_phase1_decision_bundle(bundle)
    return bundle


def validate_phase1_decision_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    """Validate the consolidated Phase 1 policy and readiness contract."""

    if not isinstance(bundle, dict):
        raise ValidationError("decision bundle must be an object")
    if set(bundle) != PHASE1_ROOT_KEYS:
        raise ValidationError("decision bundle root shape is not the approved contract")
    if bundle.get("schema_version") != "1.0":
        raise ValidationError("decision bundle schema_version must be 1.0")
    if not isinstance(bundle.get("bundle_id"), str) or not bundle["bundle_id"]:
        raise ValidationError("decision bundle requires bundle_id")

    decisions = bundle.get("decisions")
    if not isinstance(decisions, list):
        raise ValidationError("decision bundle requires a decisions list")
    decision_ids: list[str] = []
    for index, decision in enumerate(decisions, start=1):
        if not isinstance(decision, dict):
            raise ValidationError(f"decision {index} must be an object")
        if set(decision) != {"id", "status", "owner", "policy_ref"}:
            raise ValidationError(f"decision {index} shape is not the approved contract")
        decision_id = decision.get("id")
        if not isinstance(decision_id, str) or not decision_id:
            raise ValidationError(f"decision {index} requires a non-empty id")
        if decision_id in decision_ids:
            raise ValidationError(f"duplicate consolidated decision id: {decision_id}")
        if decision.get("status") != PHASE1_DECISION_STATUSES.get(decision_id):
            raise ValidationError(f"decision {decision_id} has incorrect consolidated status")
        if not isinstance(decision.get("policy_ref"), str) or not decision["policy_ref"]:
            raise ValidationError(f"decision {decision_id} requires policy_ref")
        decision_ids.append(decision_id)
    if set(decision_ids) != set(PHASE1_DECISION_IDS):
        missing = sorted(set(PHASE1_DECISION_IDS) - set(decision_ids))
        unexpected = sorted(set(decision_ids) - set(PHASE1_DECISION_IDS))
        detail = []
        if missing:
            detail.append("missing: " + ", ".join(missing))
        if unexpected:
            detail.append("unexpected: " + ", ".join(unexpected))
        raise ValidationError("consolidated decision IDs do not match P1-D001..P1-D030; " + "; ".join(detail))

    policies = bundle.get("policies")
    if not isinstance(policies, dict) or set(policies) != PHASE1_POLICY_KEYS:
        raise ValidationError("decision bundle policy shape is not complete")
    for decision in decisions:
        if _resolve_policy_ref(bundle, decision["policy_ref"]) is _MISSING:
            raise ValidationError(f"decision {decision['id']} policy_ref does not resolve")

    species = bundle.get("species")
    if not isinstance(species, list) or len(species) != len(PHASE1_SPECIES):
        raise ValidationError("decision bundle must contain exactly nine species")
    expected_species = dict(PHASE1_SPECIES)
    observed_species: dict[str, str] = {}
    for index, row in enumerate(species, start=1):
        if not isinstance(row, dict):
            raise ValidationError(f"species {index} must be an object")
        species_id = row.get("species_id")
        scientific_name = row.get("scientific_name")
        if species_id in observed_species:
            raise ValidationError(f"duplicate consolidated species_id: {species_id}")
        if species_id not in expected_species or scientific_name != expected_species[species_id]:
            raise ValidationError(f"unexpected consolidated species row: {species_id}")
        if row.get("accepted_name") != scientific_name or row.get("include_phase1") is not True:
            raise ValidationError(f"species {species_id} is not canonical and included")
        if row.get("ala_taxon_concept_id") is not None:
            raise ValidationError("ALA taxon concept IDs remain pending and must be null")
        aliases = row.get("historical_aliases")
        if not isinstance(aliases, list) or not all(isinstance(alias, str) and alias for alias in aliases):
            raise ValidationError(f"species {species_id} historical_aliases must be a string list")
        observed_species[species_id] = scientific_name

    if policies["species"] != {"focal_species_count": 9, "stable_id_field": "species_id", "canonical_name_field": "accepted_name", "historical_aliases_explicit": True, "ala_resolution": "pending_compact_scientific_check"}:
        raise ValidationError("species contract policy is incomplete")

    _require_policy(policies, "thylogale_edge_case")
    thylogale = policies["thylogale_edge_case"]
    if thylogale != {"near_ubiquitous": True, "low_contrast_at_degree_resolution": 0.01, "manufacture_class_balance": False, "prevalence_aware_evaluation": True, "pseudoabsence_generation": "disabled"}:
        raise ValidationError("Thylogale edge-case policy is incomplete")
    if thylogale.get("pseudoabsence_generation") != "disabled":
        raise ValidationError("Thylogale pseudoabsence generation must remain disabled")
    if thylogale.get("manufacture_class_balance") is not False:
        raise ValidationError("Thylogale class balance must not be manufactured")
    if thylogale.get("prevalence_aware_evaluation") is not True:
        raise ValidationError("Thylogale prevalence-aware evaluation must be retained")

    temporal = _require_policy(policies, "temporal")
    if temporal != {"primary_window": {"start": "2001-01-01", "end": "2025-12-31", "inclusive": True}, "older_records": "archive_exclude_primary", "missing_defensible_year": "exclude_primary", "retain_date_precision": True}:
        raise ValidationError("primary temporal window must be inclusive 2001-01-01 through 2025-12-31")
    quality = _require_policy(policies, "ala_quality")
    if quality != {"hard_exclusions": ["taxon_mismatch", "missing_or_invalid_coordinates", "outside_boundary", "coordinate_uncertainty_over_1000_m"], "max_coordinate_uncertainty_m": 1000, "missing_uncertainty_excluded": False, "precision_basis": ["reported", "inferred", "unknown"], "infer_precision_from_decimal_digit_count": False, "utm_undocumented_resolution": "retain_provisionally_unknown", "duplicate_record_ids": "remove_exact", "repeated_presences": "collapse_later_species_grid_with_counts_provenance", "suspect_assertions": "flag_transparently"}:
        raise ValidationError("ALA quality policy is incomplete")
    if quality.get("max_coordinate_uncertainty_m") != 1000 or quality.get("missing_uncertainty_excluded") is not False:
        raise ValidationError("ALA uncertainty policy must use a 1000 m threshold and retain missing uncertainty")
    if quality.get("precision_basis") != ["reported", "inferred", "unknown"] or quality.get("infer_precision_from_decimal_digit_count") is not False:
        raise ValidationError("ALA precision policy is contradictory")
    resources = _require_policy(policies, "ala_resources")
    if resources != {
        "scope": "broadly_all_eligible_resources",
        "resource_ids_retained": True,
        "documented_versioned_blocklist_only": True,
    }:
        raise ValidationError("ALA resource inclusion/versioned blocklist policy is incomplete")
    versioning = _require_policy(policies, "source_versioning")
    if set(versioning) != {"raw_snapshots", "query_manifests", "acquisition_timestamps", "endpoints_and_package_versions", "taxon_concept_ids", "filters_and_counts", "checksums"} or not all(versioning.values()):
        raise ValidationError("ALA result versioning policy is incomplete")

    source_combination = _require_policy(policies, "source_combination")
    if source_combination != {"accepted_presence_dominates": True, "presence_rule": "any_accepted_ala_or_camera_presence_makes_species_grid_present", "camera_absence_rule": "use_only_without_accepted_presence", "preserve_conflicts_provenance_counts": True, "absence_label": "survey_supported_absence"}:
        raise ValidationError("source-combination policy is incomplete")
    if source_combination.get("accepted_presence_dominates") is not True:
        raise ValidationError("accepted presence must dominate source combination")
    if source_combination.get("absence_label") != "survey_supported_absence":
        raise ValidationError("camera non-detection label must be survey_supported_absence")
    camera = _require_policy(policies, "camera")
    if set(camera) != {"authority", "absence", "effort"} or camera.get("authority") != "barry_authoritative_dataset":
        raise ValidationError("camera authority policy is incomplete")
    if camera["absence"] != {"label": "survey_supported_absence", "deployment_period": "broad_3_to_4_year_near_continuous", "effort_study": "none_detailed"}:
        raise ValidationError("camera survey-supported absence policy is incomplete")
    if camera["effort"] != {"retain": "essential_provenance_broad_period_absence_rule", "thresholding": "none_detailed"}:
        raise ValidationError("detailed camera effort study must remain disabled")
    pseudoabsence = _require_policy(policies, "pseudoabsence")
    if pseudoabsence != {"label": "pseudoabsence", "minimum_distinct_non_target_species": 3, "target_presence_required": False, "camera_classification_supersedes": True, "minimum_distance_km": 5, "distance_metric": "projected_metric_crs", "preserve_nearest_presence_distance": True, "thylogale_generation": "disabled"}:
        raise ValidationError("pseudoabsence policy is incomplete")
    if pseudoabsence.get("minimum_distinct_non_target_species") != 3 or pseudoabsence.get("minimum_distance_km") != 5:
        raise ValidationError("pseudoabsence thresholds must be 3 species and 5 km")
    if pseudoabsence.get("distance_metric") != "projected_metric_crs" or pseudoabsence.get("thylogale_generation") != "disabled":
        raise ValidationError("pseudoabsence metric or Thylogale rule is contradictory")
    thinning = _require_policy(policies, "thinning")
    if thinning != {"human_footprint_thinning": False, "random_or_kmeans_thinning": False, "collapse_outcome": "one_species_grid_outcome_with_observation_counts", "later_weighting": "modelling_stage_sensitivity_only"}:
        raise ValidationError("thinning policy is incomplete")
    if thinning.get("human_footprint_thinning") is not False or thinning.get("random_or_kmeans_thinning") is not False:
        raise ValidationError("acquisition-stage thinning must remain disabled")

    partition = _require_policy(policies, "spatial_partition")
    if (partition.get("microcluster_count"), partition.get("outer_test_cluster_count"), partition.get("clusters_in_cv"), partition.get("cv_fold_count")) != (50, 5, 45, 5):
        raise ValidationError("spatial partition must be 50 clusters, 5 test, 45 in 5 folds")
    if partition.get("candidate_seed_fixed") is not True or partition.get("freeze_test_set") is not True or partition.get("ecological_visual_review") != "one_permitted_before_fit" or partition.get("pre_model_score_dimensions") != ["geographic_dispersion", "environmental_regional_coverage", "usable_species_class_representation"]:
        raise ValidationError("spatial-selection procedure is incomplete")
    predictors = _require_policy(policies, "predictors")
    active_predictors = predictors.get("active_predictors")
    if predictors.get("active_predictor_count") != 28 or active_predictors != PHASE1_ACTIVE_PREDICTORS:
        raise ValidationError("predictor policy must retain exactly 28 active predictors")
    excluded_predictors = predictors.get("excluded_predictors")
    if excluded_predictors != PHASE1_EXCLUDED_PREDICTORS or len(set(active_predictors)) != 28 or len(set(excluded_predictors)) != 4 or set(active_predictors).intersection(excluded_predictors):
        raise ValidationError("predictor exclusions do not match the consolidated policy")
    if predictors.get("stack") != "tas_stack.tif" or predictors.get("source_metadata") != "recover_and_preserve_do_not_rebuild_phase1":
        raise ValidationError("predictor source authority is incomplete")
    if _require_policy(policies, "scaling") != {"continuous_scaling_fit": "training_data_only", "apply_to": ["validation", "test", "map"], "persist_parameters": True}:
        raise ValidationError("continuous scaling must be fit on training data only")
    if _require_policy(policies, "categorical_levels").get("persist") is not True:
        raise ValidationError("categorical level dictionary must be persisted")
    privacy = bundle.get("privacy")
    if not isinstance(privacy, dict) or not isinstance(privacy.get("camera"), dict):
        raise ValidationError("decision bundle requires camera privacy policy")
    camera_privacy = privacy["camera"]
    if set(privacy) != {"camera"} or set(camera_privacy) != {"maximum_public_resolution_degree", "exact_coordinates_and_site_ids", "deployment_timing_and_current_activity", "release"}:
        raise ValidationError("camera privacy shape is not the approved contract")
    if camera_privacy != {"maximum_public_resolution_degree": 0.01, "exact_coordinates_and_site_ids": "private_ignored", "deployment_timing_and_current_activity": "do_not_expose", "release": "collapsed_grid_level_evidence_only"}:
        raise ValidationError("camera public resolution cannot exceed 0.01 degree")

    grid = _require_policy(policies, "grid")
    if grid != {"source_name": "tasmanian_gridpoints.csv", "resolution_degree": 0.01, "crs": "WGS84", "alignment": "legacy_validated", "centroids": "legacy_validated", "grid_id": "stable_coordinate_derived", "grid_checksum": "required", "camera_coordinates": "UTM_transformed_to_WGS84_before_database_entry"}:
        raise ValidationError("legacy grid contract is incomplete")
    boundary = _require_policy(policies, "boundary")
    if boundary != {"coastline_source": "legacy_tasmania_coast.shp", "broad_filtering": True, "canonical_grid_controls_eligible_cells": True, "island_rules_separate": True}:
        raise ValidationError("boundary contract is incomplete")
    island = _require_policy(policies, "island_exclusions")
    if set(island) != {"apply_to", "excluded_combination_presence", "island_codes", "species_exclusions"} or island.get("apply_to") != "absence_evidence_only" or island.get("excluded_combination_presence") != "review_not_silent_delete":
        raise ValidationError("island exclusion semantics are incomplete")
    if island.get("island_codes") != PHASE1_ISLAND_CODES or island.get("species_exclusions") != PHASE1_ISLAND_MATRIX:
        raise ValidationError("approved species-by-island matrix is incomplete or malformed")
    if set(island["species_exclusions"]) != set(expected_species) or any(code not in PHASE1_ISLAND_CODES for codes in island["species_exclusions"].values() for code in codes):
        raise ValidationError("species-by-island matrix contains unknown species or island code")
    coordinate = _require_policy(policies, "coordinate_assignment")
    if coordinate != {"assignment": "containing_eligible_cell_only", "record_centroid_distance": True, "local_half_diagonal_km": 0.7, "nearest_land_cell_rescue": False, "water_lake_ineligible": "flag_or_exclude", "coordinate_uncertainty_separate": True}:
        raise ValidationError("coordinate assignment contract is incomplete")
    qa = _require_policy(policies, "qa")
    if qa != {"automated_sweeps": 1, "focused_material_repair_passes_max": 1, "two_unproductive_attempts": "stop_and_reassess", "non_negotiable": ["schema", "provenance", "spatial_validity", "deterministic_reproducibility", "source_classification", "partition_leakage", "contradictory_outcomes"], "material_diagnostics": ["missingness", "species_representation", "fold_balance", "prevalence", "spatial_coverage"], "legacy_comparisons": "diagnostic_never_automatic_targets"}:
        raise ValidationError("QA policy is incomplete")
    if qa.get("automated_sweeps") != 1 or qa.get("focused_material_repair_passes_max") != 1 or qa.get("two_unproductive_attempts") != "stop_and_reassess" or qa.get("legacy_comparisons") != "diagnostic_never_automatic_targets":
        raise ValidationError("QA sweep, Pareto repair, or legacy comparison policy is incomplete")
    if set(qa.get("non_negotiable", [])) != {"schema", "provenance", "spatial_validity", "deterministic_reproducibility", "source_classification", "partition_leakage", "contradictory_outcomes"}:
        raise ValidationError("QA non-negotiable checks are incomplete")
    if _require_policy(policies, "fixtures") != {"tracked": "small_synthetic", "real_fixture": "explicit_approval_required", "sensitive_locations": "avoid"}:
        raise ValidationError("fixture policy is incomplete")
    if _require_policy(policies, "storage") != {"raw_and_bulky_outputs": "ignored", "tracked": ["configs", "manifests", "checksums", "non_sensitive_summaries"]}:
        raise ValidationError("storage policy is incomplete")
    if _require_policy(policies, "tooling") != {"python": "minimal_standard_library_contract_scaffold", "broad_migration": False}:
        raise ValidationError("tooling policy is incomplete")
    if _require_policy(policies, "decision_bundle") != {"format": "human_readable_machine_validated_json", "single_authoritative_bundle": True, "duplicated_authoritative_values": False}:
        raise ValidationError("decision bundle authority policy is incomplete")
    if _require_policy(policies, "legacy_comparison") != {"role": "comparison_evidence_only", "canonical_inputs": False, "gate_targets": False}:
        raise ValidationError("legacy comparison role is incomplete")

    prerequisites = bundle.get("operational_prerequisites")
    if not isinstance(prerequisites, list) or {item.get("decision_id") for item in prerequisites if isinstance(item, dict)} != {"P1-D003", "P1-D008"} or len(prerequisites) != 2:
        raise ValidationError("exactly the P1-D003 and P1-D008 operational prerequisites are required")
    for item in prerequisites:
        if not isinstance(item, dict):
            raise ValidationError("live acquisition prerequisites must be objects")
        expected_keys = {"decision_id", "key", "status", "exact_query_resolution", "exact_ala_taxon_concept_ids"} if item.get("decision_id") == "P1-D003" else {"decision_id", "key", "status", "exact_local_source_path", "source_path_tracked"}
        if set(item) != expected_keys or item.get("status", "").startswith("resolved"):
            raise ValidationError("live acquisition prerequisites must remain pending")
    ala_prereq = next(item for item in prerequisites if item["decision_id"] == "P1-D003")
    camera_prereq = next(item for item in prerequisites if item["decision_id"] == "P1-D008")
    if ala_prereq.get("key") != "ala_taxon_resolution" or ala_prereq.get("status") != "pending_barry_check" or ala_prereq.get("exact_ala_taxon_concept_ids") is not None or ala_prereq.get("exact_query_resolution") is not None:
        raise ValidationError("exact ALA taxon resolution must remain unset pending Barry check")
    if camera_prereq.get("key") != "camera_source_staging" or camera_prereq.get("status") != "pending_barry_staging" or camera_prereq.get("exact_local_source_path") is not None or camera_prereq.get("source_path_tracked") is not False:
        raise ValidationError("exact camera source path must remain private and unstaged")

    return {
        "bundle_id": bundle["bundle_id"],
        "schema_version": bundle["schema_version"],
        "decision_count": len(decision_ids),
        "decision_consolidation_status": "complete",
        "live_acquisition_status": "blocked",
        "blocked_prerequisites": [
            "P1-D003:ala_taxon_resolution",
            "P1-D008:camera_source_staging",
        ],
    }


def build_phase1_decision_readiness_summary(bundle: dict[str, Any]) -> dict[str, Any]:
    """Return the deterministic policy/live-readiness split for a valid bundle."""

    return dict(validate_phase1_decision_bundle(bundle))


def _require_policy(policies: dict[str, Any], name: str) -> dict[str, Any]:
    value = policies.get(name)
    if not isinstance(value, dict):
        raise ValidationError(f"decision bundle requires policy block {name}")
    return value


_MISSING = object()


def _resolve_policy_ref(bundle: dict[str, Any], reference: str) -> Any:
    """Resolve a dotted decision reference against policies or root privacy."""

    current: Any = bundle.get("policies")
    parts = reference.split(".")
    if parts[0] == "privacy":
        current = bundle.get("privacy")
    for part in parts[1:] if parts[0] == "privacy" else parts:
        if not isinstance(current, dict) or part not in current:
            return _MISSING
        current = current[part]
    return current


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_safe_relative_path(path_text: Any, *, label: str) -> None:
    if not isinstance(path_text, str) or not path_text:
        raise ValidationError(f"{label} requires a path")
    path = Path(path_text)
    if path.is_absolute() or ".." in path.parts:
        raise ValidationError(f"{label} path is not a safe relative path: {path_text}")
    if path.parts and path.parts[0] in {"data", "temp"}:
        raise ValidationError(f"{label} path cannot target real payload directory: {path_text}")


def _validate_checksum_block(block: Any, *, label: str) -> None:
    if not isinstance(block, dict):
        raise ValidationError(f"{label} requires checksum metadata")
    algorithm = block.get("algorithm")
    value = block.get("value")
    if algorithm != "sha256":
        raise ValidationError(f"{label} checksum algorithm must be sha256")
    _validate_sha256_hex_digest(value, label=f"{label} checksum value")


def _validate_sha256_hex_digest(value: Any, *, label: str) -> None:
    if not isinstance(value, str) or len(value) != 64:
        raise ValidationError(f"{label} must be a SHA-256 hex digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValidationError(f"{label} must be a SHA-256 hex digest") from exc


def _require_non_empty_string(
    contract: dict[str, Any], field: str, source_id: str
) -> str:
    value = contract.get(field)
    if not isinstance(value, str) or not value:
        raise ValidationError(f"source contract {source_id} requires non-empty {field}")
    return value


def _require_non_empty_mapping(
    contract: dict[str, Any], field: str, source_id: str
) -> dict[str, Any]:
    value = contract.get(field)
    if not isinstance(value, dict) or not value:
        raise ValidationError(f"source contract {source_id} requires {field}")
    return value
