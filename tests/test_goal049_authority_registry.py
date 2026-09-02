import csv
import hashlib
import importlib.util
import json
import re
import shutil
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("goal049_authority_registry", ROOT / "scripts/goal049_authority_registry.py")
goal049 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(goal049)


def _abd_header():
    return [f"{i}_field" for i in range(1, 231)]


def _abd_row(name, source_id, *, core=True, habitats=(), nomadic=False, irruptive=False, family="Acanthizidae"):
    values = ["NA"] * 230
    values[6] = name
    values[9] = family
    values[16] = "1"  # field 17: species
    values[29] = "1" if core else "0"  # field 30
    values[31] = values[32] = values[33] = "0"  # fields 32-34
    for field in (67, 68, 70, 71, 72, 73):
        values[field - 1] = "Core" if core and field == 68 else "not listed"
    for field in habitats:
        values[field - 1] = "1"
    values[195] = "1" if nomadic else "0"
    values[196] = "1" if irruptive else "0"
    values[228] = str(source_id)
    return values


def _write_fixture(tmp_path):
    config = json.loads((ROOT / "config/goal049_seawfb_canonical_response.json").read_text())
    goal048 = json.loads((ROOT / "config/goal048_seawfb_bioregional_freeze.json").read_text())
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "goal049_seawfb_canonical_response.json").write_text(json.dumps(config))
    (config_dir / "goal048_seawfb_bioregional_freeze.json").write_text(json.dumps(goal048))
    taxonomy = tmp_path / "data/processed/dsdm/goal048-seawfb-bioregional-freeze/taxonomy_freeze.json"
    taxonomy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "data/processed/dsdm/goal048-seawfb-bioregional-freeze/taxonomy_freeze.json", taxonomy)
    authority = tmp_path / goal049.PRIVATE_ROOT / goal049.AUTHORITY_DIRNAME
    authority.mkdir(parents=True)

    seeds_all = goal048["species_universes"]["ecological_candidate_names"]
    names = [seeds_all[0], seeds_all[1]]
    abd_rows = [
        _abd_row(names[0], 1001, core=True),
        _abd_row(names[1], 1002, core=True, habitats=(122, 123, 124)),
        _abd_row("Effort active", 1003, habitats=(115,)),
        _abd_row("Aux active", 1004, habitats=(122,)),
        _abd_row("Nomad excluded", 1005, habitats=(122,), nomadic=True),
        _abd_row("Unmatched source", 9999, habitats=(122,)),
        _abd_row("Pyrrholaemus sagittatus", 1006, core=False),
        _abd_row("Geophaps ferruginea", 9998, habitats=(115,)),
        _abd_row("Geophaps plumifera", 1007),
    ]
    abd = authority / goal049.AUTHORITY_FILES["australian_bird_data"]
    with abd.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(_abd_header())
        writer.writerows(abd_rows)

    wlab = authority / "WLAB_v4.3.csv"
    wlab_header = ["TaxonLevel", "SpID", "TaxonScientificName", "FamilyScientificName"]
    wlab_rows = [
        ["sp", "1001", names[0], "Acanthizidae"],
        ["sp", "1002", names[1], "Pardalotidae"],
        ["sp", "1003", "Effort active", "Acanthizidae"],
        ["sp", "1004", "Aux active", "Pardalotidae"],
        ["sp", "1004", "Other exact", "Pardalotidae"],
        ["sp", "1005", "Nomad excluded", "Pardalotidae"],
        ["sp", "1006", "Pyrrholaemus sagittatus", "Acanthizidae"],
        ["sp", "1007", "Geophaps plumifera", "Columbidae"],
    ]
    with wlab.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(wlab_header)
        writer.writerows(wlab_rows)
    (authority / goal049.AUTHORITY_FILES["australian_bird_data_metadata"]).write_text("synthetic metadata\n")
    return abd, wlab, names


def test_roles_seeds_crosswalk_and_count_free_receipt(tmp_path):
    abd, wlab, seeds = _write_fixture(tmp_path)
    result = goal049.build_registry(tmp_path, abd_path=abd, wlab_path=wlab)
    rows = {row["name"]: row for row in result["registry"]["rows"]}
    assert rows["Effort active"]["effort"] is True
    assert rows["Effort active"]["auxiliary"] is False
    assert rows["Aux active"]["auxiliary"] is True
    assert rows["Aux active"]["target"] is True
    assert rows["Nomad excluded"]["effort"] is True
    assert rows["Nomad excluded"]["auxiliary"] is False
    assert rows["Unmatched source"]["auxiliary"] is True
    assert rows["Unmatched source"]["target"] is True
    assert "Geophaps ferruginea" not in rows
    assert rows["Geophaps plumifera"]["effort"] is True
    assert "Geophaps ferruginea" in rows["Geophaps plumifera"]["merged_source_names"]
    assert any(item.get("reason") == "explicit_config_reconciliation" and item["source_name"] == "Geophaps ferruginea" for item in result["exception_ledger"]["exceptions"])
    assert rows[seeds[0]]["goal048_seed"] is True
    assert rows[seeds[0]]["effort"] is False  # retained despite no active role
    assert len(result["registry"]["goal048_seed_names"]) == 100
    assert result["registry"]["marked_seed_row_count"] == 100
    assert len(result["registry"]["goal048_seed_assignment"]) == 100
    assert len(set(result["registry"]["goal048_seed_assignment"].values())) == 100
    assert all(len(row.get("seed_names", [])) == 1 for row in result["registry"]["rows"] if row.get("goal048_seed"))
    assert len({row["name"] for row in result["registry"]["rows"]}) == len(result["registry"]["rows"])
    assert result["registry"]["goal048_taxonomy_source_sha256"]
    assert rows["Pyrrholaemus sagittatus"]["goal048_seed"] is True
    assert "Pyrrholaemus sagittata" in rows["Pyrrholaemus sagittatus"]["seed_names"]
    assert any(item["type"] == "unmatched_crosswalk" and item["source_name"] == "Unmatched source" for item in result["exception_ledger"]["exceptions"])
    assert any(item["type"] == "resolved_authority_exception" and item["source_name"] == "Aux active" for item in result["exception_ledger"]["exceptions"])
    assert result["registry"]["occurrence_queries"] == 0
    assert result["registry"]["model_outcomes"] == 0
    receipt = json.loads((tmp_path / "metadata/goal049_registry_receipt.json").read_text())
    assert receipt["privacy"] == {"coordinates_written": False, "private_species_cell_lists_written": False, "raw_occurrence_rows": 0, "model_outcomes": 0}
    assert not (tmp_path / "metadata/goal049_registry_taxonomy_freeze.json").exists()
    assert not (tmp_path / goal049.PRIVATE_ROOT / "taxonomy_freeze.json").exists()


def test_authority_hashes_and_private_registry_schema(tmp_path):
    abd, wlab, _ = _write_fixture(tmp_path)
    result = goal049.build_registry(tmp_path, abd_path=abd, wlab_path=wlab)
    registry = result["registry"]
    metadata = abd.parent / goal049.AUTHORITY_FILES["australian_bird_data_metadata"]
    assert registry["authority_sha256"] == {"wlab": hashlib.sha256(wlab.read_bytes()).hexdigest(), "australian_bird_data": hashlib.sha256(abd.read_bytes()).hexdigest(), "australian_bird_data_metadata": hashlib.sha256(metadata.read_bytes()).hexdigest()}
    assert registry["goal048_taxonomy_source_sha256"]
    private = json.loads((tmp_path / goal049.PRIVATE_ROOT / "registry.json").read_text())
    assert private["rows"] == registry["rows"]
    assert {"name", "source_name", "source_id", "birdlife_spid", "effort", "auxiliary", "target", "reason"} <= set(private["rows"][0])
    assert not any("latitude" in json.dumps(value).lower() or "longitude" in json.dumps(value).lower() for value in private["rows"])


def test_source_has_no_occurrence_query_or_count_interface():
    source = (ROOT / "scripts/goal049_authority_registry.py").read_text()
    assert "galah" not in source.lower()
    assert "atlas_counts" not in source.lower()
    assert not re.search(r"(?:search_taxa|occurrence_status|lat_long)", source, re.I)


def test_xlsx_requires_openpyxl_or_reads_with_maintained_parser(tmp_path):
    path = tmp_path / "fixture.xlsx"
    path.write_bytes(b"not-an-xlsx")
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        with pytest.raises(goal049.Goal049Error, match="openpyxl"):
            goal049.read_wlab(path)
    else:
        with pytest.raises(Exception):
            goal049.read_wlab(path)


def test_abd_cp1252_fallback(tmp_path):
    path = tmp_path / "abd_cp1252.csv"
    row = _abd_row("Species \u2013 with dash", 7)
    with path.open("wb") as stream:
        stream.write((",".join(_abd_header()) + "\n").encode("ascii"))
        stream.write((",".join(row) + "\n").encode("cp1252"))
    parsed = goal049.read_abd(path)
    assert parsed[0][goal049.ABD_NAME_FIELD] == "Species \u2013 with dash"


def test_legacy_spid_reuse_requires_name_evidence_and_exact_fallback(tmp_path):
    abd, wlab, _ = _write_fixture(tmp_path)
    with abd.open("a", newline="") as stream:
        csv.writer(stream).writerow(_abd_row("Ninox leucopsis", 5054, habitats=(115,), family="Strigidae"))
        csv.writer(stream).writerow(_abd_row("Legacy transition", 1008, habitats=(115,), family="Acanthizidae"))
    with wlab.open("a", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["sp", "5054", "Calidris mauri", "Scolopacidae"])
        writer.writerow(["sp", "8741", "Ninox leucopsis", "Strigidae"])
        writer.writerow(["sp", "1008", "Current transition", "Acanthizidae"])
    result = goal049.build_registry(tmp_path, abd_path=abd, wlab_path=wlab)
    rows = {row["source_name"]: row for row in result["registry"]["rows"]}
    assert rows["Ninox leucopsis"]["name"] == "Ninox leucopsis"
    assert rows["Ninox leucopsis"]["birdlife_spid"] == "8741"
    assert any(item.get("reason") == "exact_name_fallback_after_legacy_spid_conflict" and item["source_name"] == "Ninox leucopsis" for item in result["exception_ledger"]["exceptions"])
    assert rows["Legacy transition"]["name"] == "Current transition"
    assert any(item.get("reason") == "reviewed_same_family_legacy_name_transition" and item["source_name"] == "Legacy transition" for item in result["exception_ledger"]["exceptions"])


def test_split_inheritance_preserves_distinct_malurus_seed(tmp_path):
    abd, wlab, _ = _write_fixture(tmp_path)
    with abd.open("a", newline="") as stream:
        csv.writer(stream).writerow(_abd_row("Malurus lamberti", 1010, habitats=(122,), family="Maluridae"))
    with wlab.open("a", newline="") as stream:
        csv.writer(stream).writerow(["sp", "1010", "Malurus assimilis", "Maluridae"])
    result = goal049.build_registry(tmp_path, abd_path=abd, wlab_path=wlab)
    rows = {row["name"]: row for row in result["registry"]["rows"]}
    assert rows["Malurus assimilis"]["source_name"] == "Malurus lamberti"
    assert rows["Malurus lamberti"]["goal048_seed"] is True
    assert rows["Malurus lamberti"]["effort"] is True
    assert rows["Malurus lamberti"]["auxiliary"] is True
    assert rows["Malurus lamberti"]["birdlife_spid"] is None
    assert any(item.get("reason") == "split_derived_trait_inheritance" and item["source_name"] == "Malurus lamberti" for item in result["exception_ledger"]["exceptions"])
