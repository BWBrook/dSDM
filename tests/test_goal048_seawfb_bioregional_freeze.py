from importlib import import_module
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import unquote

import pytest

import pandas as pd
import galah

SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
goal048 = import_module("goal048_seawfb_bioregional_freeze")
census = import_module("goal048_aggregate_census")
Goal048Error = goal048.Goal048Error
compile_query = goal048.compile_query
validate_freezes = goal048.validate_freezes

FILTERS = [
    "year>=2001", "year<=2025", "occurrenceStatus=PRESENT", "spatiallyValid=true",
    "decimalLongitude>=135.375", "decimalLongitude<=153.625",
    "decimalLatitude>=-43.6275", "decimalLatitude<=-22.7575",
]


def test_query_object_is_identical_except_for_facet():
    identifiers = ["parent", "subspecies", "alias"]
    total = compile_query(identifiers, FILTERS, None)
    facet = compile_query(identifiers, FILTERS, "lat_long")
    assert total["identifiers"] == facet["identifiers"]
    assert total["filters"] == facet["filters"]
    assert facet["group_by"] == "lat_long"


def test_query_requires_all_coordinate_bounds():
    with pytest.raises(Goal048Error, match="coordinate filters"):
        compile_query(["parent"], FILTERS[:-1], None)


def test_live_stage_rejects_historical_galah(monkeypatch):
    monkeypatch.setattr(goal048.galah, "__version__", "0.13.3")
    with pytest.raises(Goal048Error, match="explicit uv --with overlay"):
        goal048._require_galah_overlay()


@pytest.mark.skipif(galah.__version__ != "0.13.6", reason="real repaired serializer requires the Goal048 overlay")
def test_galah_identifier_union_and_filters_compile_closed_and_identically(monkeypatch):
    counts = import_module("galah.atlas_counts")
    taxonomy = import_module("galah.search_taxa")
    monkeypatch.setattr(
        taxonomy, "search_taxa",
        lambda **_: pd.DataFrame({"taxonConceptID": ["parent", "child"]}),
    )
    base = counts.add_taxa(identifiers=["parent", "child"], atlas="Australia", URL="https://example.invalid?")
    total = counts.add_filters(URL=base, atlas="Australia", filters=FILTERS)
    facet = counts.add_filters(URL=base, atlas="Australia", filters=FILTERS) + "&facets=lat_long&flimit=-1&pageSize=0"
    decoded_total = unquote(total)
    decoded_facet = unquote(facet)
    assert 'lsid:"parent" OR lsid:"child"' in decoded_total
    for expected in FILTERS:
        field = expected.split("=", 1)[0].rstrip("<>")
        assert field in decoded_total
        assert field in decoded_facet
    assert decoded_facet.removesuffix("&facets=lat_long&flimit=-1&pageSize=0") == decoded_total


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _sha_value(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _make_freeze_tree(root: Path):
    private = root / "data/processed/dsdm/goal048-seawfb-bioregional-freeze"
    private.mkdir(parents=True)
    cells = private / "domain_cells.csv"
    cells.write_text("cell_id,row,column,longitude,latitude\nr0000c0000,0,0,135.375,-43.6275\n")
    values = {
        "domain": {"status": "frozen_count_free", "cell_count": 1, "private_cells_sha256": hashlib.sha256(cells.read_bytes()).hexdigest()},
        "taxonomy": {"status": "frozen_count_free", "species_count": 100, "parent_count": 100, "descendant_count": 247, "alias_count": 179},
        "roles": {"status": "frozen_response_blind", "row_count": 100, "role_counts": {"effort": 96, "auxiliary": 71, "target": 71}},
        "nvis": {"status": "frozen_count_free", "rows": [{"code": code} for code in list(range(1, 33)) + [99]]},
    }
    paths = {}
    for name, value in values.items():
        path = private / f"{'role' if name == 'roles' else name}_freeze.json"
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
        paths[name] = path
    manifest = {
        name: {"status": value["status"], "semantic_sha256": _sha_value(value), "private_receipt": str(paths[name].relative_to(root)), "private_receipt_sha256": hashlib.sha256(paths[name].read_bytes()).hexdigest(), **({"cell_count": 1} if name == "domain" else {})}
        for name, value in values.items()
    }
    manifest["joint_sha256"] = _sha_value(manifest)
    metadata = root / "metadata"
    metadata.mkdir()
    path = metadata / "goal048_prerequisite_freeze.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return path, cells


def test_freeze_validator_fails_on_joint_manifest_tamper(tmp_path):
    manifest_path, _ = _make_freeze_tree(tmp_path)
    manifest = json.loads(manifest_path.read_text())
    manifest["taxonomy"]["species_count"] = 99
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    with pytest.raises(Goal048Error, match="joint checksum"):
        validate_freezes(tmp_path)


def test_freeze_validator_fails_on_domain_cell_tamper(tmp_path):
    _, cells = _make_freeze_tree(tmp_path)
    cells.write_text(cells.read_text() + "r0000c0001,0,1,135.385,-43.6275\n")
    with pytest.raises(Goal048Error, match="cell ledger"):
        validate_freezes(tmp_path)


def test_census_plan_preserves_frozen_order_and_query_identity(tmp_path, monkeypatch):
    private = tmp_path / "data/processed/dsdm/goal048-seawfb-bioregional-freeze"
    private.mkdir(parents=True)
    names = [f"Species {index:03d}" for index in range(100)]
    config = tmp_path / "config"
    config.mkdir()
    (config / "goal048_seawfb_bioregional_freeze.json").write_text(json.dumps({"species_universes": {"ecological_candidate_names": names}}))
    rows = [{"seed_name": name, "ordered_identifiers": [f"id-{index}"]} for index, name in enumerate(names)]
    (private / "taxonomy_freeze.json").write_text(json.dumps({"rows": rows}))
    (private / "domain_freeze.json").write_text(json.dumps({"bbox": {"xmin": 135.375, "xmax": 153.625, "ymin": -43.6275, "ymax": -22.7675}}))
    role_rows = [{"name": name, "effort": index < 96} for index, name in enumerate(names)]
    (private / "role_freeze.json").write_text(json.dumps({"row_count": 100, "role_counts": {"effort": 96}, "rows": role_rows}))
    monkeypatch.setattr(census, "validate_freezes", lambda _: {"status": "validated_count_free", "roles": {"private_receipt_sha256": "role-receipt"}})
    plan = census.build_census_plan(tmp_path)
    assert [item["species"] for item in plan] == names[:96]
    assert len({item["query_fingerprint"] for item in plan}) == 96
    assert {item["role_receipt_sha256"] for item in plan} == {"role-receipt"}
    partition = census._role_partition(tmp_path, names, {"roles": {"private_receipt_sha256": "role-receipt"}})
    assert len(partition["eligible"]) == 96
    assert len(partition["excluded"]) == 4
    assert all(row["status"] == "not_queried_frozen_role_exclusion" for row in partition["excluded"])
    for item in plan:
        assert item["total_query"]["identifiers"] == item["facet_query"]["identifiers"]
        assert item["total_query"]["filters"] == item["facet_query"]["filters"]


def _make_resume_checkpoint(root: Path, *, fingerprint: str = "query-a", count: int = 1):
    private = root / "data/processed/dsdm/goal048-seawfb-bioregional-freeze"
    (private / "domain_cells.csv").parent.mkdir(parents=True, exist_ok=True)
    domain_rows = "".join(f"r0000c{index:04d},0,{index},135.{375 + index:03d},-43.6275\n" for index in range(count))
    (private / "domain_cells.csv").write_text("cell_id,row,column,longitude,latitude\n" + domain_rows)
    cells_dir = private / "census/cells"
    cells_dir.mkdir(parents=True)
    metadata = root / "metadata"
    metadata.mkdir()
    (metadata / "goal048_prerequisite_freeze.json").write_text(json.dumps({"joint_sha256": "prerequisite"}))
    plan = []
    for index in range(count):
        species = "Species A" if index == 0 else f"Species {index}"
        cells = cells_dir / f"{index:03d}.json"
        cells.write_text(json.dumps({"species": species, "cells": [f"r0000c{index:04d}"]}, indent=2) + "\n")
        counts = {"total_count": 3, "facet_count_sum": 3, "facet_group_count": 2}
        checkpoint = {
            "status": "passed", "index": index, "species": species,
            "source": "live_galah_aggregate",
            "query_fingerprint": fingerprint if index == 0 else f"query-{index}", "prerequisite_joint_sha256": "prerequisite",
            **counts, "count_conservation_sha256": _sha_value(counts),
            "retained_species_cell_count": 1, "private_cell_receipt": str(cells.relative_to(root)),
            "private_cell_receipt_sha256": hashlib.sha256(cells.read_bytes()).hexdigest(),
        }
        path = private / "census/checkpoints" / f"{index:03d}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(checkpoint, indent=2, sort_keys=True) + "\n")
        plan.append({"index": index, "species": species, "query_fingerprint": "query-a" if index == 0 else f"query-{index}"})
    return plan


def test_resume_is_deterministic_and_idempotent(tmp_path):
    plan = _make_resume_checkpoint(tmp_path)
    first = census.load_resume_state(tmp_path, plan)
    second = census.load_resume_state(tmp_path, plan)
    assert first == second
    assert len(first) == 1


def test_resume_loads_domain_ledger_once_for_multiple_checkpoints(tmp_path, monkeypatch):
    plan = _make_resume_checkpoint(tmp_path, count=2)
    original = census._domain_cell_frame
    reads = 0

    def counted_read(root):
        nonlocal reads
        reads += 1
        return original(root)

    monkeypatch.setattr(census, "_domain_cell_frame", counted_read)
    completed = census.load_resume_state(tmp_path, plan)
    assert len(completed) == 2
    assert reads == 1


def test_resume_rejects_checkpoint_tamper(tmp_path):
    plan = _make_resume_checkpoint(tmp_path, fingerprint="tampered")
    with pytest.raises(Goal048Error, match="authority drift"):
        census.load_resume_state(tmp_path, plan)


def test_resume_rejects_orphan_cell_receipt(tmp_path):
    plan = _make_resume_checkpoint(tmp_path)
    orphan = tmp_path / "data/processed/dsdm/goal048-seawfb-bioregional-freeze/census/cells/001.json"
    orphan.write_text(json.dumps({"species": "orphan", "cells": []}))
    with pytest.raises(Goal048Error, match="orphan or missing"):
        census.load_resume_state(tmp_path, plan)


def test_cumulative_group_ceiling_is_exact():
    assert census._enforce_cumulative_groups(9_250_000, 750_000) == 10_000_000
    with pytest.raises(Goal048Error, match="cumulative census group ceiling"):
        census._enforce_cumulative_groups(9_250_001, 750_000)


def test_canary_reuse_rejects_query_tamper(tmp_path, monkeypatch):
    private = tmp_path / "data/processed/dsdm/goal048-seawfb-bioregional-freeze"
    private.mkdir(parents=True)
    cells = private / "canary_species_cells.json"
    cells.write_text(json.dumps({"species": "Acanthiza pusilla", "cells": []}) + "\n")
    evidence = tmp_path / "evidence/seawfb_bioregional_freeze/goal048"
    evidence.mkdir(parents=True)
    (evidence / "aggregate_canary.json").write_text(json.dumps({
        "query_fingerprint": "frozen", "prerequisite_joint_sha256": "prerequisite",
        "private_species_cell_sha256": hashlib.sha256(cells.read_bytes()).hexdigest(),
    }))
    monkeypatch.setattr(census, "validate", lambda _: {"status": "passed"})
    with pytest.raises(Goal048Error, match="not reusable"):
        census._reuse_canary(tmp_path, {"index": 2, "species": "Acanthiza pusilla", "query_fingerprint": "tampered"}, "prerequisite")


def test_run_species_uses_two_identical_queries_and_writes_cells(tmp_path, monkeypatch):
    private = tmp_path / "data/processed/dsdm/goal048-seawfb-bioregional-freeze"
    private.mkdir(parents=True)
    (private / "domain_cells.csv").write_text("cell_id,row,column,longitude,latitude\nr0000c0000,0,0,135.375,-43.6275\n")
    item = {
        "index": 0,
        "species": "Species A",
        "query_fingerprint": "fingerprint",
        "total_query": {"identifiers": ["id-a"], "filters": ["decimalLongitude>=135"]},
        "facet_query": {"identifiers": ["id-a"], "filters": ["decimalLongitude>=135"], "group_by": "lat_long"},
    }
    calls = []

    def fake_counts(**query):
        calls.append(query)
        return pd.DataFrame({"totalRecords": [2]}) if len(calls) == 1 else pd.DataFrame({"lat_long": ["[-43.6275,135.375]"], "count": [2]})

    monkeypatch.setattr(census.galah, "atlas_counts", fake_counts)
    checkpoint = census._run_species(tmp_path, item, "prerequisite")
    assert calls == [item["total_query"], item["facet_query"]]
    assert checkpoint["facet_count_sum"] == checkpoint["total_count"] == 2
    assert checkpoint["retained_species_cell_count"] == 1
    receipt = json.loads((private / "census/cells/000.json").read_text())
    assert receipt["cells"] == ["r0000c0000"]


def test_run_species_rejects_truncated_aggregate(tmp_path, monkeypatch):
    private = tmp_path / "data/processed/dsdm/goal048-seawfb-bioregional-freeze"
    private.mkdir(parents=True)
    (private / "domain_cells.csv").write_text("cell_id,row,column,longitude,latitude\nr0000c0000,0,0,135.375,-43.6275\n")
    item = {
        "index": 0, "species": "Species A", "query_fingerprint": "fingerprint",
        "total_query": {"identifiers": ["id-a"], "filters": ["decimalLongitude>=135"]},
        "facet_query": {"identifiers": ["id-a"], "filters": ["decimalLongitude>=135"], "group_by": "lat_long"},
    }
    response = pd.DataFrame({"totalRecords": [2]})
    response.attrs["truncated"] = True
    monkeypatch.setattr(census.galah, "atlas_counts", lambda **_: response)
    with pytest.raises(Goal048Error, match="truncation"):
        census._run_species(tmp_path, item, "prerequisite")
