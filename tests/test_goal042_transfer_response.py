from __future__ import annotations

import copy
import json
from decimal import Decimal
from pathlib import Path

import pytest

import dsdm_phase1.goal042_transfer_response as response
from dsdm_phase1.goal040_support import GEOD


ROOT = Path(__file__).parents[1]


def _point(origin: tuple[float, float], distance_m: float) -> tuple[Decimal, Decimal]:
    lon, lat = GEOD.fwd(*origin, 90.0, distance_m)[:2]
    return Decimal(str(lon)), Decimal(str(lat))


def test_mainland_materialiser_excludes_target_and_preserves_nested_rules():
    target = "target"
    origin = (145.0, -35.0)
    coordinates = {
        "presence": (Decimal("145"), Decimal("-35")),
        "near5": _point(origin, 2_000),
        "far2": _point(origin, 6_000),
        "far3": _point(origin, 7_000),
        "far5": _point(origin, 8_000),
    }
    members = {
        "presence": {target, "a", "b", "c"},
        "near5": {"a", "b", "c", "d", "e"},
        "far2": {"a", "b"},
        "far3": {"a", "b", "c"},
        "far5": {"a", "b", "c", "d", "e"},
    }
    rows = {row["cell_id"]: row for row in response.materialise_mainland_rows(target, coordinates, members, {"presence"})}
    assert rows["presence"]["other_species_count"] == 3
    assert not rows["presence"]["eligible_x2"]
    assert not rows["near5"]["eligible_x2"]
    assert rows["far2"]["eligible_x2"] and not rows["far2"]["eligible_x3"]
    assert rows["far3"]["eligible_x2"] and rows["far3"]["eligible_x3"] and not rows["far3"]["eligible_x5"]
    assert rows["far5"]["eligible_x2"] and rows["far5"]["eligible_x3"] and rows["far5"]["eligible_x5"]


def test_materialiser_uses_only_the_presence_set_authorised_by_caller():
    target = "target"
    origin = (145.0, -35.0)
    coordinates = {
        "p_authorised": (Decimal("145"), Decimal("-35")),
        "candidate": _point(origin, 8_000),
        "p_withheld": _point(origin, 9_000),
    }
    base_members = {
        "p_authorised": {target},
        "candidate": {"a", "b", "c"},
    }
    authorised = response.materialise_mainland_rows(target, coordinates, base_members, {"p_authorised"})
    assert next(row for row in authorised if row["cell_id"] == "candidate")["eligible_x3"]
    with_withheld = copy.deepcopy(base_members)
    with_withheld["p_withheld"] = {target}
    leaked = response.materialise_mainland_rows(
        target, coordinates, with_withheld, {"p_authorised", "p_withheld"}
    )
    assert not next(row for row in leaked if row["cell_id"] == "candidate")["eligible_x3"]


def test_tasmania_presence_precedence_and_absence_are_evidence_only():
    rows = {
        row["cell_id"]: row
        for row in response.materialise_tasmania_rows(
            "target", {"ala", "both"}, {"camera", "both"}, {"ala", "absence"}
        )
    }
    assert rows["ala"]["response"] == 1
    assert rows["ala"]["camera_survey_supported_absence"]
    assert rows["both"]["response"] == 1
    assert rows["camera"]["response"] == 1
    assert rows["absence"]["response"] == 0
    assert set(rows) == {"ala", "both", "camera", "absence"}


def test_live_tracked_manifest_is_structurally_valid():
    assert response.validate(ROOT, require_raw=False) == {
        "status": "tracked_goal042_valid_raw_replay_required",
        "raw_replay_required": True,
    }


def test_manifest_gate_rejects_tasmania_background_claim():
    manifest = json.loads((ROOT / response.MANIFEST_PATH).read_text(encoding="utf-8"))
    authorities, _, _, _ = response._authorities(ROOT, require_raw=False)
    manifest["summary"]["firewall"]["target_group_background_rows_in_tasmania_output"] = 1
    with pytest.raises(response.Goal042Error, match="firewall"):
        response._validate_manifest(manifest, authorities["bindings"])


def test_manifest_gate_requires_the_exact_other_nineteen_heads():
    manifest = json.loads((ROOT / response.MANIFEST_PATH).read_text(encoding="utf-8"))
    authorities, _, _, _ = response._authorities(ROOT, require_raw=False)
    target = "Dasyurus maculatus"
    manifest["summary"]["cohort"]["cross_species_pretraining_heads_by_target"][target][0] = "invented taxon"
    with pytest.raises(response.Goal042Error, match="firewall"):
        response._validate_manifest(manifest, authorities["bindings"])


def test_manifest_gate_rejects_a_tracked_cell_identity():
    manifest = json.loads((ROOT / response.MANIFEST_PATH).read_text(encoding="utf-8"))
    authorities, _, _, _ = response._authorities(ROOT, require_raw=False)
    first = next(iter(manifest["summary"]["mainland_reference"].values()))
    first["cell_id"] = "private"
    with pytest.raises(response.Goal042Error, match="private"):
        response._validate_manifest(manifest, authorities["bindings"])
