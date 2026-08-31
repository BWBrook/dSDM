from importlib import import_module
import hashlib
import importlib.util
import json
from pathlib import Path
from urllib.parse import unquote

import pytest

import pandas as pd
import galah

SCRIPT = Path(__file__).parents[1] / "scripts/goal048_seawfb_bioregional_freeze.py"
SPEC = importlib.util.spec_from_file_location("goal048_seawfb_bioregional_freeze", SCRIPT)
assert SPEC and SPEC.loader
goal048 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(goal048)
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
