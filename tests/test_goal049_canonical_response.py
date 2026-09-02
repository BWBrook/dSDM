from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import goal049_canonical_response as canonical
import validate_goal049_seawfb_canonical_response as validator


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _upstream_tree(root: Path) -> Path:
    config = {
        "upstream": {"goal048_selected_regions": ["NCP", "SEH", "NNC"], "external_training_exclusion_km": 50.0},
        "roles": {"focal_exclusion": {"from_auxiliary_pretraining": True}},
        "panels": {"two_of_three_panel": False},
        "effort_support": {"primary_x": 10, "evaluation_only_sensitivity_x": 20, "require_x20_subset_of_x10": True},
        "estimability": {
            "evaluation_minimum_presence_cells_per_target_region": 30, "evaluation_minimum_x10_background_cells_per_target_region": 100,
            "evaluation_minimum_50km_tiles_per_class": 4, "training_minimum_presence_cells_per_target": 200,
            "training_minimum_x10_background_cells_per_target": 500, "training_minimum_spatial_tiles_per_class": 4,
            "common_primary_target_panel_minimum": 20,
        },
        "occurrence_contract": {
            "time_start": "2001-01-01", "time_end": "2025-12-31", "occurrence_status": "PRESENT", "spatially_valid": True,
            "snap_immediately_to_resolution_degree": 0.01,
            "transport_ceiling": {"lat_long_groups_per_species": 750000, "lat_long_groups_total": 50000000, "private_disk_gib": 4, "peak_ram_gib": 8},
        },
        "tracked_outputs": {
            "canary": str(canonical.CANARY), "progress": str(canonical.PROGRESS),
            "completion": "evidence/seawfb_canonical_response/goal049/completion_receipt.json",
            "panel_summary": "evidence/seawfb_canonical_response/goal049/panel_summary.json",
        },
    }
    _write(root / canonical.CONFIG, config)
    domain = pd.DataFrame({"cell_id": ["r0000c0000", "r0000c0001"], "row": [0, 0], "column": [0, 1], "longitude": [1.005, 1.015], "latitude": [2.005, 2.005]})
    domain_path = root / canonical.DOMAIN
    domain_path.parent.mkdir(parents=True, exist_ok=True); domain.to_csv(domain_path, index=False)
    domain_receipt = {"status": "frozen_count_free", "cell_count": 2, "private_cells_sha256": _sha(domain_path), "bbox": {"xmin": 1.005, "xmax": 1.015, "ymin": 2.005, "ymax": 2.005}}
    _write(root / canonical.DOMAIN_RECEIPT, domain_receipt)
    _write(root / canonical.GOAL048_RESOLUTION, {"selected_regions": ["NCP", "SEH", "NNC"]})
    _write(root / canonical.GOAL048_SELECTION, {"status": "selected_after_explicit_resolution", "selected_design": {"regions": ["NCP", "SEH", "NNC"]}})
    registry = {"rows": [{"name": "Species alpha", "effort": True, "auxiliary": True, "target": True}]}
    _write(root / canonical.REGISTRY, registry)
    taxonomy_rows = [{"species": "Species alpha", "active": True, "roles": {"effort": True, "auxiliary": True, "target": True}, "ordered_identifiers": ["id-alpha"]}]
    taxonomy = {"status": "frozen_count_free", "rows": taxonomy_rows, "ledger_sha256": canonical._digest(taxonomy_rows)}
    _write(root / canonical.TAXONOMY, taxonomy)
    stage = {"status": "passed", "occurrence_support_queried": False, "config_sha256": _sha(root / canonical.CONFIG), "registry_sha256": _sha(root / canonical.REGISTRY), "taxonomy_private_sha256": _sha(root / canonical.TAXONOMY)}
    _write(root / canonical.STAGE_A, stage)
    normalisation = canonical._expected_normalisation(domain, 0.01)
    query = canonical._expected_query_fingerprint(config, domain_receipt, ["id-alpha"])
    private_receipt = root / canonical.PRIVATE / "species_cells/00000.json"
    receipt = {"species": "Species alpha", "cells": ["r0000c0000"], "query_fingerprint": query, "identifiers_sha256": canonical._digest(["id-alpha"]), "domain_cells_sha256": _sha(domain_path), "domain_cell_count": 2, "domain_freeze_sha256": _sha(root / canonical.DOMAIN_RECEIPT), "normalisation": normalisation, "occurrence_rows_downloaded": 0}
    _write(private_receipt, receipt)
    counts = {"total_count": 4, "facet_count_sum": 4, "facet_group_count": 2}
    checkpoint = {"status": "passed", "index": 0, "species": "Species alpha", "query_fingerprint": query, "stage_a_freeze_sha256": _sha(root / canonical.STAGE_A), **counts, "count_conservation_sha256": canonical._digest(counts), "occurrence_rows_downloaded": 0, "model_outcome_counter": 0, "private_cell_receipt": str(private_receipt.relative_to(root)), "private_cell_receipt_sha256": _sha(private_receipt), "retained_species_cell_count": 1, "private_disk_bytes_after": 100, "peak_ram_bytes_upper_bound": 100}
    checkpoint_path = root / canonical.PRIVATE / "checkpoints/00000.json"; _write(checkpoint_path, checkpoint)
    progress = {"status": "complete", "stage_a_freeze_sha256": _sha(root / canonical.STAGE_A), "planned_species": 1, "completed_species": 1, "cumulative_total_count": 4, "cumulative_facet_groups": 2, "cumulative_retained_species_cells": 1, "checkpoint_inventory_sha256": canonical._digest([_sha(checkpoint_path)]), "private_disk_bytes": 100, "peak_ram_bytes_upper_bound": 100, "occurrence_rows_downloaded": 0, "model_outcome_counter": 0}
    _write(root / canonical.PROGRESS, progress)
    _write(root / canonical.PRIVATE / "run.exit", {"status": "complete", "completed_species": 1, "cumulative_facet_groups": 2})
    extra = root / canonical.PRIVATE / "canary_species_cells.json"; _write(extra, receipt)
    canary = {"status": "passed", "species": "Species alpha", "source": "live_galah_aggregate", **counts, "query_fingerprint": query, "identifiers_sha256": canonical._digest(["id-alpha"]), "domain_cells_sha256": _sha(domain_path), "domain_cell_count": 2, "domain_freeze_sha256": _sha(root / canonical.DOMAIN_RECEIPT), "normalisation_sha256": canonical._digest(normalisation), "stage_a_freeze_sha256": _sha(root / canonical.STAGE_A), "count_conservation_sha256": canonical._digest(counts), "private_cell_receipt": str(extra.relative_to(root)), "private_cell_receipt_sha256": _sha(extra), "occurrence_rows_downloaded": 0, "model_outcome_counter": 0}
    _write(root / canonical.CANARY, canary)
    return root


def _small_thresholds() -> dict[str, int]:
    return {
        "x10": 2, "x20": 3,
        "eval_presence": 2, "eval_background": 2, "eval_tiles": 2,
        "train_presence": 2, "train_background": 2, "train_tiles": 2,
        "common_minimum": 1,
    }


def test_focal_exclusion_changes_only_focal_presence_cells():
    presence = np.array([True, False, True, False])
    richness = np.array([3, 3, 2, 1])
    excluded, x10, x20 = canonical.focal_background_masks(
        presence, richness, focal_is_effort_donor=True, x10=2, x20=3,
    )
    np.testing.assert_array_equal(excluded, [2, 3, 1, 1])
    np.testing.assert_array_equal(x10, [False, True, False, False])
    np.testing.assert_array_equal(x20, [False, True, False, False])
    np.testing.assert_array_equal(excluded[~presence], richness[~presence])


def test_x20_is_nested_and_focal_presence_never_becomes_background():
    presence = np.array([True, False, False, False])
    richness = np.array([21, 20, 10, 9])
    _, x10, x20 = canonical.focal_background_masks(
        presence, richness, focal_is_effort_donor=True, x10=10, x20=20,
    )
    np.testing.assert_array_equal(x10, [False, True, True, False])
    np.testing.assert_array_equal(x20, [False, True, False, False])
    assert np.all(~x20 | x10)


def test_training_complement_excludes_all_three_buffers_simultaneously():
    buffers = {
        "NCP": np.array([True, False, False, False, False]),
        "SEH": np.array([False, True, False, False, False]),
        "NNC": np.array([False, False, True, False, False]),
    }
    np.testing.assert_array_equal(
        canonical.training_mask_from_buffers(buffers),
        [False, False, False, True, True],
    )


def test_gate_metrics_keep_evaluation_and_buffer_separated_training_distinct():
    xy = np.array([
        [0.0, 0.0], [50_000.0, 0.0], [100_000.0, 0.0], [150_000.0, 0.0],
        [200_000.0, 0.0], [250_000.0, 0.0], [300_000.0, 0.0], [350_000.0, 0.0],
    ])
    evaluation = np.array([True, True, True, True, False, False, False, False])
    training = np.array([False, False, False, False, True, True, True, True])
    presence = np.array([True, True, False, False, True, True, False, False])
    x10 = np.array([False, False, True, True, False, False, True, True])
    x20 = np.array([False, False, True, False, False, False, True, False])
    result = canonical.gate_metrics(presence, x10, x20, evaluation, training, xy, _small_thresholds())
    assert result["evaluation_presence_cells"] == 2
    assert result["training_presence_cells"] == 2
    assert result["evaluation_x10_background_tiles"] == 2
    assert result["training_x10_background_tiles"] == 2
    assert result["training_pass"] is True
    assert result["evaluation_x10_pass"] is True
    assert result["evaluation_x20_pass_diagnostic"] is False


def test_anchored_tile_count_handles_negative_coordinates_and_duplicates():
    xy = np.array([[0, 0], [49_999, 49_999], [50_000, 0], [-1, -1]], dtype=float)
    assert canonical.anchored_tile_count(xy, np.ones(4, dtype=bool)) == 3


def _panel_rows() -> pd.DataFrame:
    rows = []
    for species, passes in {
        "Species common": {"NCP": True, "SEH": True, "NNC": True},
        "Species regional": {"NCP": True, "SEH": False, "NNC": False},
    }.items():
        for region in canonical.SELECTED_REGIONS:
            rows.append({
                "species": species, "region": region, "training_pass": True,
                "evaluation_x10_pass": passes[region],
                "evaluation_x20_pass_diagnostic": False,
            })
    return pd.DataFrame(rows)


def test_panel_derivation_has_one_common_and_three_region_specific_panels():
    frame, common, secondary = canonical.derive_panel_membership(_panel_rows(), common_minimum=1)
    assert common == ["Species common"]
    assert secondary == {
        "NCP": ["Species common", "Species regional"],
        "SEH": ["Species common"],
        "NNC": ["Species common"],
    }
    assert frame.loc[frame.species == "Species common", "primary_common_member"].all()
    assert not frame.loc[frame.species == "Species regional", "primary_common_member"].any()


def test_common_panel_minimum_fails_closed_without_weakening_gates():
    with pytest.raises(canonical.Goal049CanonicalError, match="fewer than 2"):
        canonical.derive_panel_membership(_panel_rows(), common_minimum=2)


def test_canonical_parquet_validator_detects_provenance_content_drift(tmp_path):
    path = tmp_path / "canonical.parquet"
    pq.write_table(pa.table({"species": ["Species a", "Species a"], "cell_id": ["r0000c0001", "r0000c0002"]}), path)
    assert validator._validate_canonical_stream(path, [("Species a", ["r0000c0001", "r0000c0002"])]) == 2
    with pytest.raises(validator.Goal049ValidationError, match="differs"):
        validator._validate_canonical_stream(path, [("Species a", ["r0000c0001", "r0000c0003"])])


@pytest.mark.parametrize(
    "payload",
    [
        {"cell_ids": ["r0000c0001"]},
        {"safe": {"latitude": -42.0}},
        {"safe": ["r0000c0001"]},
    ],
)
def test_tracked_privacy_guard_rejects_cell_or_coordinate_payloads(payload):
    with pytest.raises(canonical.Goal049CanonicalError, match="privacy|cell identifier"):
        canonical._validate_privacy(payload)


def test_threshold_provenance_drift_is_rejected():
    config = {
        "upstream": {"goal048_selected_regions": ["NCP", "SEH", "NNC"]},
        "panels": {"two_of_three_panel": False},
        "effort_support": {"primary_x": 11, "evaluation_only_sensitivity_x": 20, "require_x20_subset_of_x10": True},
        "estimability": {
            "evaluation_minimum_presence_cells_per_target_region": 30,
            "evaluation_minimum_x10_background_cells_per_target_region": 100,
            "evaluation_minimum_50km_tiles_per_class": 4,
            "training_minimum_presence_cells_per_target": 200,
            "training_minimum_x10_background_cells_per_target": 500,
            "training_minimum_spatial_tiles_per_class": 4,
            "common_primary_target_panel_minimum": 20,
        },
    }
    with pytest.raises(canonical.Goal049CanonicalError, match="contract drift"):
        canonical._thresholds(config)


def test_upstream_replay_accepts_exact_noncontiguous_canary_receipt(tmp_path):
    inputs = canonical._load_upstream(_upstream_tree(tmp_path))
    assert inputs["canary"]["species"] == "Species alpha"
    assert inputs["totals"]["memberships"] == 1


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("canary_query", "canary conservation or query/domain binding drift"),
        ("normalisation_origin", "query/domain binding drift"),
        ("retained_count", "count or identifier drift"),
        ("transport", "transport ceiling failed"),
        ("role_snapshot", "roles no longer match"),
    ],
)
def test_upstream_replay_fails_on_material_binding_drift(tmp_path, mutation, message):
    root = _upstream_tree(tmp_path)
    if mutation == "canary_query":
        value = json.loads((root / canonical.CANARY).read_text()); value["query_fingerprint"] = "drift"; _write(root / canonical.CANARY, value)
    elif mutation == "normalisation_origin":
        path = root / canonical.PRIVATE / "species_cells/00000.json"; value = json.loads(path.read_text()); value["normalisation"]["grid_origin"][0] += 0.01; _write(path, value)
        checkpoint_path = root / canonical.PRIVATE / "checkpoints/00000.json"; checkpoint = json.loads(checkpoint_path.read_text()); checkpoint["private_cell_receipt_sha256"] = _sha(path); _write(checkpoint_path, checkpoint)
        progress_path = root / canonical.PROGRESS; progress = json.loads(progress_path.read_text()); progress["checkpoint_inventory_sha256"] = canonical._digest([_sha(checkpoint_path)]); _write(progress_path, progress)
    elif mutation == "retained_count":
        path = root / canonical.PRIVATE / "checkpoints/00000.json"; value = json.loads(path.read_text()); value["retained_species_cell_count"] = 2; _write(path, value)
        progress_path = root / canonical.PROGRESS; progress = json.loads(progress_path.read_text()); progress["checkpoint_inventory_sha256"] = canonical._digest([_sha(path)]); _write(progress_path, progress)
    elif mutation == "transport":
        path = root / canonical.PRIVATE / "checkpoints/00000.json"; value = json.loads(path.read_text()); value["facet_group_count"] = 750001; value["count_conservation_sha256"] = canonical._digest({key: value[key] for key in ("total_count", "facet_count_sum", "facet_group_count")}); _write(path, value)
        progress_path = root / canonical.PROGRESS; progress = json.loads(progress_path.read_text()); progress["checkpoint_inventory_sha256"] = canonical._digest([_sha(path)]); _write(progress_path, progress)
    else:
        path = root / canonical.TAXONOMY; value = json.loads(path.read_text()); value["rows"][0]["roles"]["target"] = False; value["ledger_sha256"] = canonical._digest(value["rows"]); _write(path, value)
        stage_path = root / canonical.STAGE_A; stage = json.loads(stage_path.read_text()); stage["taxonomy_private_sha256"] = _sha(path); _write(stage_path, stage)
        stage_sha = _sha(stage_path)
        checkpoint_path = root / canonical.PRIVATE / "checkpoints/00000.json"; checkpoint = json.loads(checkpoint_path.read_text()); checkpoint["stage_a_freeze_sha256"] = stage_sha; _write(checkpoint_path, checkpoint)
        progress_path = root / canonical.PROGRESS; progress = json.loads(progress_path.read_text()); progress["stage_a_freeze_sha256"] = stage_sha; progress["checkpoint_inventory_sha256"] = canonical._digest([_sha(checkpoint_path)]); _write(progress_path, progress)
        canary_path = root / canonical.CANARY; canary = json.loads(canary_path.read_text()); canary["stage_a_freeze_sha256"] = stage_sha; _write(canary_path, canary)
    with pytest.raises(canonical.Goal049CanonicalError, match=message):
        canonical._load_upstream(root)


def test_final_privacy_scan_covers_every_available_tracked_json(tmp_path):
    safe = tmp_path / "safe.json"; leaked = tmp_path / "leaked.json"
    _write(safe, {"status": "passed"}); _write(leaked, {"note": "contains r0000c0001 privately"})
    config = {"tracked_outputs": {"safe": "safe.json", "leaked": "leaked.json"}}
    with pytest.raises(canonical.Goal049CanonicalError, match="cell identifier"):
        canonical._privacy_scan_tracked(tmp_path, config)


def test_independent_validator_rejects_surplus_panel_columns():
    expected = pd.DataFrame({"species": ["Species alpha"], "region": ["NCP"]})
    observed = expected.assign(latitude=-42.0)
    with pytest.raises(validator.Goal049ValidationError, match="surplus columns"):
        validator._assert_exact_panel_frame(observed, expected)
