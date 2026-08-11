from __future__ import annotations

import copy
import json
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

import dsdm_phase1.goal040_support as support


ROOT = Path(__file__).parents[1]


def test_precedence_and_distinct_target_exclusion():
    assert support._precedence("a", {"a"}, {"a"}) == "presence"
    assert support._precedence("a", set(), {"a"}) == "camera_survey_supported_absence"
    assert support._precedence("a", set(), set()) == "unknown"
    members = {"target", "donor_one", "donor_two"}
    assert len(members) - int("target" in members) == 2


def test_wgs84_distance_boundary_below_and_tied_neighbours():
    origin = (145.0, -35.0)
    exact_point = support.GEOD.fwd(*origin, 90.0, 5000.0)[:2]
    below_point = support.GEOD.fwd(*origin, 90.0, 4999.0)[:2]
    presence = [(Decimal(str(origin[0])), Decimal(str(origin[1])))]
    exact = support._nearest_geodesic_m([(Decimal(str(exact_point[0])), Decimal(str(exact_point[1])))], presence)[0]
    below = support._nearest_geodesic_m([(Decimal(str(below_point[0])), Decimal(str(below_point[1])))], presence)[0]
    assert exact >= support.DISTANCE_M - 1e-8 and support._far_enough(exact)
    assert below < support.DISTANCE_M and not support._far_enough(below)
    east = support.GEOD.fwd(*origin, 90.0, 10000.0)[:2]
    west = support.GEOD.fwd(*origin, 270.0, 10000.0)[:2]
    tied = support._nearest_geodesic_m(
        [(Decimal(str(origin[0])), Decimal(str(origin[1])))],
        [(Decimal(str(east[0])), Decimal(str(east[1]))), (Decimal(str(west[0])), Decimal(str(west[1])))],
    )[0]
    assert tied == pytest.approx(10000.0)


def test_adaptive_refinement_finds_geodesic_nearest_outside_projected_first_hit():
    query = (141.39198502654375, -43.20704989173352)
    projected_first = (142.92703027778884, -42.32907056965435)
    geodesic_first = (139.4769970359221, -43.38422716216662)
    px, py = support.TRANSFORM.transform(
        [projected_first[0], geodesic_first[0]], [projected_first[1], geodesic_first[1]]
    )
    qx, qy = support.TRANSFORM.transform(*query)
    projected_index = int(support.cKDTree(np.column_stack((px, py))).query([qx, qy], k=1)[1])
    assert projected_index == 0
    result = support._nearest_geodesic_m(
        [(Decimal(str(query[0])), Decimal(str(query[1])))],
        [(Decimal(str(projected_first[0])), Decimal(str(projected_first[1]))), (Decimal(str(geodesic_first[0])), Decimal(str(geodesic_first[1])))],
    )[0]
    expected = support.GEOD.inv(*query, *geodesic_first)[2]
    assert result == pytest.approx(expected)


def test_output_receipt_rejects_schema_drift(tmp_path):
    path = tmp_path / support.DIAGNOSTICS_FILE
    path.write_text("bad\n", encoding="utf-8")
    with pytest.raises(support.Goal040SupportError, match="schema"):
        support._file_receipt(path)


def _tracked_fixture():
    manifest = json.loads((ROOT / support.SUPPORT_MANIFEST_PATH).read_text(encoding="utf-8"))
    bindings, denominators = support._tracked_authorities(ROOT)
    return manifest, bindings, denominators


def test_tracked_gate_rejects_donor_rule_drift():
    manifest, bindings, denominators = _tracked_fixture()
    manifest["rules"]["donors"] = "camera_and_target_may_be_donors"
    with pytest.raises(support.Goal040SupportError, match="rule"):
        support._validate_tracked_manifest_payload(manifest, bindings, denominators)


def test_tracked_gate_rejects_negative_aggregate_count():
    manifest, bindings, denominators = _tracked_fixture()
    first = next(iter(manifest["summary"]["target_region"].values()))
    first["donor_count_histogram_0_to_20"]["0"] = -1
    with pytest.raises(support.Goal040SupportError, match="histogram"):
        support._validate_tracked_manifest_payload(manifest, bindings, denominators)


def test_tracked_gate_rejects_privacy_flag_drift():
    manifest, bindings, denominators = _tracked_fixture()
    manifest["privacy"]["cell_ids_retained"] = True
    with pytest.raises(support.Goal040SupportError, match="privacy"):
        support._validate_tracked_manifest_payload(manifest, bindings, denominators)


def test_tracked_gate_rejects_malformed_receipt_hash():
    manifest, bindings, denominators = _tracked_fixture()
    receipt = manifest["outputs"]["private_output_roles"]["sparse_support_diagnostics"]
    receipt["sha256"] = "0" * 63
    with pytest.raises(support.Goal040SupportError, match="receipt"):
        support._validate_tracked_manifest_payload(manifest, bindings, denominators)


def test_tracked_gate_treats_well_formed_replacement_hash_as_structural_only():
    manifest, bindings, denominators = _tracked_fixture()
    receipt = manifest["outputs"]["private_output_roles"]["sparse_support_diagnostics"]
    receipt["sha256"] = "0" * 64
    support._validate_tracked_manifest_payload(manifest, bindings, denominators)


def test_contract_gate_rejects_support_fact_drift():
    contract = json.loads((ROOT / support.CONTRACT_PATH).read_text(encoding="utf-8"))
    contract = copy.deepcopy(contract)
    contract["target_group_support"]["fact"] = "raw_observation_count"
    with pytest.raises(support.Goal040SupportError, match="contract"):
        support._validate_contract_payload(contract)
