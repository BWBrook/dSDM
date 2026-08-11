from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads(
    (ROOT / "config/goal040_se_mammal_feasibility.json").read_text(encoding="utf-8")
)


def test_domain_taxonomy_and_count_blind_tiers_are_frozen():
    domain = CONTRACT["domain"]
    assert domain == {
        "frame_authority": "future_se_bird_0p01_wgs84_frame",
        "crs": "EPSG:4326",
        "resolution_degree": 0.01,
        "cell_centroid_bbox": {
            "longitude_min": 135.375,
            "longitude_max": 153.625,
            "latitude_min": -43.6275,
            "latitude_max": -23.7775,
        },
        "eligible_cells": "land_only",
        "regions": ["southeast_mainland", "tasmania"],
        "historical_se_files_role": "archaeological_check_only_not_input",
        "boundary_authority": {
            "selection_stage": "count_free_taxonomy_and_domain_freeze",
            "tracked_manifest": "metadata/goal040_domain_boundary_manifest.json",
            "required_product_scope": "authoritative_Australian_land_and_state_boundaries",
            "required_manifest_fields": [
                "product_name", "product_version", "publisher", "source_url",
                "retrieved_at", "source_identity", "sha256", "crs", "licence",
            ],
            "cell_eligibility": "centroid_in_land_polygon_after_deterministic_bbox_clip",
            "region_classification": "centroid_in_tasmania_state_polygon_else_southeast_mainland",
            "must_be_frozen_before_count_query": True,
        },
    }
    assert CONTRACT["time"] == {"start_year": 2001, "end_year": 2025, "inclusive": True}
    taxonomy = CONTRACT["taxonomy"]
    assert taxonomy["tracked_ledger"] == "metadata/goal040_taxon_query_ledger.csv"
    assert taxonomy["raw_discovery_responses_tracked"] is False
    assert {"source_citations", "query_roles", "descendant_concepts", "synonyms"} <= set(taxonomy["required_ledger_fields"])
    assert taxonomy["occurrences_establish_eligibility"] is False
    assert taxonomy["performance_based_pruning"] is False
    assert set(taxonomy["expected_shared_anchors"]) == {
        "Notamacropus rufogriseus", "Trichosurus vulpecula",
        "Pseudocheirus peregrinus", "Vombatus ursinus", "Dasyurus maculatus",
    }
    tiers = CONTRACT["data_sufficiency_tiers"]
    assert tiers["frozen_before_count_inspection"] is True
    assert tiers["support_observed"]["minimum_distinct_post_qc_cells_any_region"] == 1
    assert tiers["mainland_pretraining_candidate"]["minimum_distinct_post_qc_mainland_cells"] == 100
    assert tiers["shared_evaluation_candidate"] == {
        "minimum_distinct_post_qc_mainland_cells": 100,
        "minimum_distinct_post_qc_tasmania_cells": 30,
    }


def test_acquisition_response_and_support_boundaries_are_frozen():
    acquisition = CONTRACT["acquisition"]
    assert acquisition["package"] == {"name": "galah-python", "version": "0.13.3"}
    assert acquisition["email_env"] == "ALA_DOWNLOAD_EMAIL" and "email" not in acquisition
    assert acquisition["store_email"] is False and acquisition["authenticate"] is False
    assert acquisition["manifest_policy"] == "immutable_identity_addressed"
    assert acquisition["raw_and_row_level_tracked"] is False
    assert acquisition["resource_ceiling"]["outside_ceiling_action"] == "stop_for_resource_route_decision_without_sampling"
    assert acquisition["qa"]["reported_uncertainty_exclusion_threshold_m"] == 1000
    assert acquisition["qa"]["deduplicate_by_provider_record_identity"] is True

    states = ["presence", "camera_survey_supported_absence", "target_group_background_candidate", "unknown"]
    response = CONTRACT["response"]
    assert response["states"] == response["precedence"] == states
    assert response["camera_absence_contributes_donor_support"] is False
    assert response["target_group_is_true_absence"] is False
    assert response["target_group_is_occupancy_nondetection"] is False
    assert response["labels_materialised_per_split"] is True
    assert response["global_final_binary_labels"] is False
    assert response["shared_materialised_universe_across_methods"] is True

    support = CONTRACT["target_group_support"]
    assert support["exclude_target"] is True
    assert support["primary_threshold"] == 3 and support["sensitivity_thresholds"] == [2, 5]
    assert support["required_nesting"] == "X5_subset_X3_subset_X2"
    assert support["minimum_nearest_target_presence_distance_m"] == 5000
    assert support["split_allowed_records_only"] is True
    assert support["camera_concordance_role"] == "aggregate_diagnostic_only_not_threshold_selection"


def test_predictor_estimand_privacy_and_stopping_contracts_are_frozen():
    estimands = CONTRACT["future_estimands"]
    assert estimands["claims_conflated"] is False
    assert len({estimands["cross_species_transfer"], estimands["same_species_geographic_transfer"], estimands["target_only_mainland_control"]}) == 3

    predictors = CONTRACT["predictors"]
    assert predictors["selection"] == "largest_defensible_common_panel"
    assert predictors["region_specific_fallback"] is False
    assert predictors["tasmania_full28_is_automatically_portable"] is False
    assert predictors["historical_se_maps_are_automatically_portable"] is False
    assert predictors["pilot"]["response_neutral"] is True
    assert predictors["pilot"]["selection_inputs"] == ["frozen_land_mask", "region", "cell_geometry"]
    assert predictors["unproven_common_source_action"] == "repair_or_blocked"

    assert CONTRACT["tracked_evidence"]["aggregate_and_privacy_safe_only"] is True
    assert CONTRACT["tracked_evidence"]["taxon_query_ledger_is_tracked"] is True
    assert CONTRACT["tracked_evidence"]["donor_identity_ban_scope"] == "no_donor_to_cell_associations_or_cell_level_donor_identity_disclosure"
    assert "donor_to_cell_identities" in CONTRACT["tracked_evidence"]["forbidden"]
    assert CONTRACT["decision"]["allowed"] == ["ready", "repair", "blocked"]
    ready = set(CONTRACT["decision"]["ready_requires"])
    assert "boundary_manifest_frozen" in ready
    assert "all_five_expected_anchors_evaluated_and_tiers_reported" in ready
    assert "all_five_expected_anchors_shared_evaluation_candidates" not in ready
    assert "at_least_5_shared_evaluation_candidates" in ready
    assert {"model_fitting", "performance_based_selection", "maps", "outer_access"} <= set(CONTRACT["forbidden_work"])
