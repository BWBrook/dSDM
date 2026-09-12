import json

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import torch

from dsdm_phase1.goal052_checkpoints import (
    _LEAF_SCHEMA,
    _atomic_bytes,
    checkpoint_paths,
    load_leaf,
    load_pretraining,
    save_leaf,
    save_pretraining,
)
from dsdm_phase1.seawfb_modeling import SeawfbModelingError, sha256_file


def _key():
    return {"identity": {"protocol": "goal052"}, "target": "Species/unsafe name", "held_fold": 2, "arm": "target_only"}


def test_checkpoint_paths_are_digest_named_and_kind_specific(tmp_path):
    key = _key()
    pre_payload, pre_receipt = checkpoint_paths(tmp_path, "pretraining", key)
    leaf_payload, leaf_receipt = checkpoint_paths(tmp_path, "leaves", key)
    assert pre_payload.suffix == ".pt"
    assert leaf_payload.suffix == ".parquet"
    assert pre_receipt.suffix == leaf_receipt.suffix == ".json"
    assert pre_payload.stem == leaf_payload.stem == pre_receipt.stem == leaf_receipt.stem
    assert "/" not in pre_payload.stem and "unsafe" not in pre_payload.stem
    assert checkpoint_paths(tmp_path, "pretraining", dict(reversed(list(key.items())))) == (pre_payload, pre_receipt)
    with pytest.raises(SeawfbModelingError, match="checkpoint_key_dimensions_missing"):
        checkpoint_paths(tmp_path, "pretraining", {"identity": {"x": 1}})


def test_pretraining_roundtrip_and_orphan_payload_is_absent(tmp_path):
    key = _key()
    state = {"stem.weight": torch.ones(2, 3), "stem.bias": torch.zeros(2)}
    saved = save_pretraining(tmp_path, key, state, {"fit": {"seed": 7}})
    loaded = load_pretraining(tmp_path, key)
    assert loaded is not None
    recovered, receipt = loaded
    assert saved["key"] == key == receipt["key"]
    assert saved["model_sha256"] == sha256_file(checkpoint_paths(tmp_path, "pretraining", key)[0])
    assert torch.equal(recovered["stem.weight"], state["stem.weight"])

    payload, receipt_path = checkpoint_paths(tmp_path, "pretraining", {**key, "target": "orphan"})
    payload.parent.mkdir(parents=True, exist_ok=True)
    torch.save(state, payload)
    assert load_pretraining(tmp_path, {**key, "target": "orphan"}) is None
    assert receipt_path.exists() is False


def test_pretraining_corruption_and_nonfinite_state_fail_closed(tmp_path):
    key = _key()
    state = {"weight": torch.ones(2)}
    save_pretraining(tmp_path, key, state, {})
    payload, receipt_path = checkpoint_paths(tmp_path, "pretraining", key)
    payload.write_bytes(b"corrupt")
    with pytest.raises(SeawfbModelingError, match="pretraining_payload_digest_mismatch"):
        load_pretraining(tmp_path, key)

    with pytest.raises(SeawfbModelingError, match="checkpoint_state_nonfinite"):
        save_pretraining(tmp_path, {**key, "target": "nan"}, {"weight": torch.tensor([float("nan")])}, {})

    receipt = json.loads(receipt_path.read_text())
    receipt["key"] = {**key, "target": "tampered"}
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(SeawfbModelingError, match="pretraining_key_mismatch"):
        load_pretraining(tmp_path, key)


def test_leaf_roundtrip_is_canonical_and_checks_expected_order_and_labels(tmp_path):
    key = _key()
    cells = ["c001", "c002", "c003"]
    labels = np.array([0, 1, 0], dtype=np.int8)
    scores = np.array([0.05, 0.8, 0.4], dtype=np.float64)
    saved = save_leaf(tmp_path, key, cells, labels, scores, {"fit": {"seed": 9}})
    loaded = load_leaf(tmp_path, key, cells, labels)
    assert loaded is not None
    recovered, receipt = loaded
    assert np.array_equal(recovered, scores)
    assert receipt["prediction_sha256"] == saved["prediction_sha256"]
    payload, _ = checkpoint_paths(tmp_path, "leaves", key)
    table = pq.read_table(payload)
    assert table.schema == _LEAF_SCHEMA
    assert table.column_names == ["cell_id", "y", "score"]
    with pytest.raises(SeawfbModelingError, match="leaf_cell_order_mismatch"):
        load_leaf(tmp_path, key, cells[::-1], labels[::-1])
    with pytest.raises(SeawfbModelingError, match="leaf_labels_mismatch"):
        load_leaf(tmp_path, key, cells, np.array([1, 1, 0], dtype=np.int8))


def test_leaf_corrupt_committed_payload_and_invalid_scores_fail_closed(tmp_path):
    key = _key()
    cells = ["c1", "c2"]
    labels = np.array([0, 1], dtype=np.int8)
    save_leaf(tmp_path, key, cells, labels, [0.1, 0.9], {})
    payload, receipt_path = checkpoint_paths(tmp_path, "leaves", key)

    bad_schema = pa.table({"cell_id": cells, "y": labels, "score": [0.1, 0.9], "extra": [1, 2]})
    pq.write_table(bad_schema, payload)
    receipt = json.loads(receipt_path.read_text())
    receipt["prediction_sha256"] = sha256_file(payload)
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(SeawfbModelingError, match="leaf_schema_invalid"):
        load_leaf(tmp_path, key, cells, labels)

    bad_scores = pa.Table.from_arrays(
        [pa.array(cells), pa.array(labels, type=pa.int8()), pa.array([0.1, float("nan")], type=pa.float64())],
        schema=_LEAF_SCHEMA,
    )
    pq.write_table(bad_scores, payload)
    receipt["prediction_sha256"] = sha256_file(payload)
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(SeawfbModelingError, match="leaf_scores_invalid"):
        load_leaf(tmp_path, key, cells, labels)


def test_leaf_rejects_out_of_range_labels_before_int8_narrowing(tmp_path):
    with pytest.raises(SeawfbModelingError, match="leaf_labels_invalid"):
        save_leaf(tmp_path, _key(), ["c1"], np.asarray([256], dtype=np.int64), [0.5], {})
    with pytest.raises(SeawfbModelingError, match="leaf_rows_invalid"):
        save_leaf(tmp_path, _key(), ["c1"], np.asarray([[1]], dtype=np.int8), [0.5], {})
    with pytest.raises(SeawfbModelingError, match="leaf_rows_invalid"):
        save_leaf(tmp_path, _key(), ["c1"], np.asarray([1], dtype=np.int8), [[0.5]], {})


def test_atomic_writer_removes_temporary_file_after_failure(tmp_path):
    destination = tmp_path / "x" / "payload.bin"

    def fail(_path):
        raise OSError("deliberate")

    with pytest.raises(OSError, match="deliberate"):
        _atomic_bytes(destination, fail, ".bin")
    assert list(destination.parent.iterdir()) == []
