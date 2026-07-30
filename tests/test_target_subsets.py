from __future__ import annotations

import pytest


def make_rows(n=17):
    from dsdm_phase1.modeling_contract import RowSet

    return RowSet.from_records([
        {
            "species_id": "sp",
            "grid_cell_id": f"cell{i:02d}",
            "pa": int(i % 3 == 0),
            "pa_type": "presence" if i % 3 == 0 else ("pseudoabsence" if i % 2 else "survey_supported_absence"),
            "microcluster": f"mc{i % 4}",
        }
        for i in range(n)
    ])


def test_endpoint_sizes_round_half_up():
    from dsdm_phase1.target_subsets import endpoint_sizes

    assert all(endpoint_sizes(n)["fraction25"] == (n + 2) // 4 for n in range(1, 18))
    assert [endpoint_sizes(n)["fraction50"] for n in range(1, 6)] == [1, 1, 2, 2, 3]


def test_ladders_nested_deterministic_and_aliases():
    from dsdm_phase1.target_subsets import build_ladders, validate_ladders

    rows = make_rows()
    a = build_ladders(rows)
    b = build_ladders(rows)
    assert {k: v.keys for k, v in a.items()} == {k: v.keys for k, v in b.items()}
    validate_ladders(rows, a)
    for ladder in ("ladder00", "ladder01", "ladder02"):
        k25 = set(a[("fraction25", ladder)].keys)
        k50 = set(a[("fraction50", ladder)].keys)
        k100 = set(a[("fraction100", ladder)].keys)
        assert k25 <= k50 <= k100 == set(rows.keys)
        assert a[("fraction100", ladder)].full_alias_id == "full"
        assert a[("fraction100", ladder)].ladder_id == "full"
    assert a[("fraction100", "ladder00")] is a[("fraction100", "ladder01")] is a[("fraction100", "ladder02")]


def test_input_order_invariance_and_validation():
    from dsdm_phase1.modeling_contract import RowSet
    from dsdm_phase1.target_subsets import build_ladders, validate_ladders

    rows = make_rows()
    reversed_rows = RowSet(tuple(reversed(rows.keys)), rows.pa[::-1], tuple(reversed(rows.response_source)), tuple(reversed(rows.microcluster)))
    assert build_ladders(rows)[("fraction50", "ladder01")].keys == build_ladders(reversed_rows)[("fraction50", "ladder01")].keys
    with pytest.raises(Exception):
        build_ladders(RowSet.from_records([{**{"species_id": "sp", "grid_cell_id": "x", "pa": 1, "pa_type": "presence"}, "microcluster": None}]))


def test_tampered_endpoint_and_exact_prefix_rejected():
    from dataclasses import replace
    from dsdm_phase1.target_subsets import build_ladders, validate_ladders

    rows = make_rows()
    endpoints = dict(build_ladders(rows))
    endpoint = endpoints[("fraction25", "ladder00")]
    endpoints[("fraction25", "ladder00")] = replace(endpoint, subset_digest="0" * 64)
    with pytest.raises(ValueError, match="tampered"):
        validate_ladders(rows, endpoints)
    endpoints = dict(build_ladders(rows))
    endpoints[("fraction25", "ladder00")] = replace(endpoints[("fraction25", "ladder00")], fraction_id="fraction50")
    with pytest.raises(ValueError, match="metadata"):
        validate_ladders(rows, endpoints)


def test_single_class_training_rejected():
    from dsdm_phase1.modeling_contract import RowSet
    from dsdm_phase1.target_subsets import build_ladders

    rows = RowSet.from_records([{"species_id": "sp", "grid_cell_id": "a", "pa": 1, "pa_type": "presence", "microcluster": "mc"}])
    with pytest.raises(ValueError, match="single_class"):
        build_ladders(rows)
