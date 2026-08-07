"""Private-substrate adapter and deidentified real-data bundle contract.

Only this module is allowed to know about the Phase 1 substrate.  The bundle
written here contains numeric arrays and aggregate metadata; it never contains
row keys, coordinates, or source payloads.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

CONTINUOUS_PREDICTORS = (
    "annmeantemp", "meandiurnrange", "isothermality", "tempseason",
    "maxtempwarmmonth", "mintempcoldmonth", "tempannrange", "meantempwetq",
    "meantempdryq", "meantempwarmq", "meantempcoldq", "annprecip",
    "precipwetmonth", "precipdrymonth", "precipseason", "precipwetq",
    "precipdryq", "precipwarmq", "precipcoldq", "elevation", "top_roughness",
    "dist_fw", "dist_road", "fpar", "human_footprint",
)
CATEGORICAL_LEVELS = {
    "soil_class": tuple(range(2, 15)),
    "veg_mvg": (1, 2, 3, 4, 5, 7, 9, 10, 11, 15, 16, 17, 18, 19, 21, 22, 24, 25, 26, 27, 29, 31),
    "landuse_secondary": (1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18),
}
CATEGORICAL_PREDICTORS = tuple(CATEGORICAL_LEVELS)
FEATURE_NAMES = CONTINUOUS_PREDICTORS + tuple(
    f"{name}__{level}" for name, levels in CATEGORICAL_LEVELS.items() for level in levels
)
REAL_SPECIES = (
    "thylogale_billardierii", "notamacropus_rufogriseus", "trichosurus_vulpecula",
    "pseudocheirus_peregrinus", "vombatus_ursinus", "sarcophilus_harrisii",
    "dasyurus_maculatus", "dasyurus_viverrinus",
)
PROVENANCE = {"presence", "survey_supported_absence", "pseudoabsence"}
ROLES = ("discovery", "stopping", "replay", "inner_assessment")
PORTABLE_ARRAYS = ("x_discovery", "y_discovery", "x_stopping", "y_stopping", "x_replay", "y_replay", "x_held")
_MANIFEST_KEYS = {
    "schema_version", "goal_id", "case_id", "target", "held_fold", "stopping_fold",
    "architecture_id", "seed", "base_seed", "transform", "input_columns", "array_shapes",
    "array_digests", "source_binding_digest", "outer_attempted", "outer_opened",
    "goal032_config_digest", "authority_digests", "auxiliary_aggregate_digest", "bundle_digest",
}


class RealDataError(ValueError):
    """Raised when the private-to-bundle contract is violated."""


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    target: str
    held_fold: str
    architecture: str
    seed: int

    @property
    def stopping_fold(self) -> str:
        index = int(self.held_fold[-2:])
        return f"fold{(index + 1) % 5:02d}"

    @property
    def transform(self) -> str:
        return f"cv_{self.held_fold}"


@dataclass(frozen=True)
class RealDataBundle:
    case: CaseSpec
    x_discovery: np.ndarray
    y_discovery: np.ndarray
    x_stopping: np.ndarray
    y_stopping: np.ndarray
    x_replay: np.ndarray
    y_replay: np.ndarray
    x_inner_assessment: np.ndarray
    y_inner_assessment: np.ndarray
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        for name in ROLES:
            x = np.asarray(getattr(self, f"x_{name}"))
            y = np.asarray(getattr(self, f"y_{name}"))
            if x.ndim != 2 or x.shape[1] != 77 or x.dtype != np.float32:
                raise RealDataError(f"invalid {name} predictors")
            if y.ndim != 1 or len(y) != len(x) or y.dtype != np.float32:
                raise RealDataError(f"invalid {name} response")
            if not np.isfinite(x).all() or not np.isfinite(y).all() or not np.isin(y, (0.0, 1.0)).all():
                raise RealDataError(f"invalid {name} values")
            x.flags.writeable = False
            y.flags.writeable = False
            object.__setattr__(self, f"x_{name}", x)
            object.__setattr__(self, f"y_{name}", y)


def _json_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _membership_digest(records: Sequence[Mapping[str, Any]]) -> str:
    """Hash source membership without serialising any membership values."""
    membership = sorted(
        f"{record['species']}|{record['cell']}|{record['fold']}|{record['source']}"
        for record in records
    )
    return hashlib.sha256("\n".join(membership).encode()).hexdigest()


def _authority_digests(config: Mapping[str, Any] | None) -> dict[str, str]:
    bindings = config.get("bindings", {}) if isinstance(config, Mapping) else {}
    return {
        name: str(bindings.get(name, {}).get("sha256", "unbound"))
        for name in ("goal029_config", "goal026_feature_contract", "goal026_fit_parameters")
    }


def _config_digest(config: Mapping[str, Any] | None, root: str | Path | None = None) -> str:
    if isinstance(config, Mapping):
        source_digest = config.get("_source_sha256")
        if isinstance(source_digest, str) and len(source_digest) == 64:
            try:
                bytes.fromhex(source_digest)
            except ValueError as exc:
                raise RealDataError("Goal032 config source digest invalid") from exc
            return source_digest
    if root is not None:
        candidate = Path(root) / "config" / "dsdm_real_compute_calibration.json"
        if candidate.is_file():
            return hashlib.sha256(candidate.read_bytes()).hexdigest()
    return _json_digest(config if config is not None else {"goal_id": "goal032-dsdm-real-compute-calibration"})


def _array_values(bundle: RealDataBundle) -> dict[str, np.ndarray]:
    return {name: np.asarray(bundle.x_inner_assessment if name == "x_held" else getattr(bundle, name)) for name in PORTABLE_ARRAYS}


def _portable_manifest(bundle: RealDataBundle, config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    metadata = dict(bundle.metadata)
    arrays = _array_values(bundle)
    authorities = dict(metadata.get("authority_digests", _authority_digests(config)))
    if config is not None:
        authorities = _authority_digests(config)
    summary_digest = metadata.get("auxiliary_aggregate_digest")
    if not summary_digest:
        summary = metadata.get("auxiliary_summary", {
            "species_count": metadata.get("auxiliary_species_count", 0),
            "fold_count": 4,
            "presence_rows": metadata.get("auxiliary_presence_rows", 0),
            "survey_absence_rows": metadata.get("auxiliary_survey_absence_rows", 0),
            "pseudoabsence_rows": metadata.get("auxiliary_pseudoabsence_rows", 0),
            "unseen_category_counts": metadata.get("unseen_category_counts", {}),
        })
        summary_digest = _json_digest(summary)
    manifest = {
        "schema_version": "goal032-real-bundle-v2",
        "goal_id": "goal032-dsdm-real-compute-calibration",
        "case_id": bundle.case.case_id,
        "target": bundle.case.target,
        "held_fold": bundle.case.held_fold,
        "stopping_fold": bundle.case.stopping_fold,
        "architecture_id": bundle.case.architecture,
        "seed": int(bundle.case.seed),
        "base_seed": int(metadata.get("base_seed", bundle.case.seed)),
        "transform": bundle.case.transform,
        "input_columns": 77,
        "array_shapes": {name: list(value.shape) for name, value in arrays.items()},
        "array_digests": {name: hashlib.sha256(value.tobytes(order="C")).hexdigest() for name, value in arrays.items()},
        "source_binding_digest": str(metadata.get("source_binding_digest", "unbound")),
        "outer_attempted": int(metadata.get("outer_attempted", 0)),
        "outer_opened": int(metadata.get("outer_opened", 0)),
        "goal032_config_digest": str(metadata.get("goal032_config_digest", _config_digest(config))),
        "authority_digests": authorities,
        "auxiliary_aggregate_digest": str(summary_digest),
    }
    return manifest


def _digest_manifest_and_arrays(manifest: Mapping[str, Any], arrays: Mapping[str, np.ndarray]) -> str:
    canonical = dict(manifest)
    canonical.pop("bundle_digest", None)
    digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode())
    for name in PORTABLE_ARRAYS:
        digest.update(name.encode())
        digest.update(np.asarray(arrays[name]).tobytes(order="C"))
    return digest.hexdigest()


def _encode(record: Mapping[str, Any]) -> np.ndarray:
    raw = record.get("x", record.get("continuous"))
    if raw is None or len(raw) != 25:
        raise RealDataError("continuous predictor contract")
    vector = [float(value) for value in raw]
    for name, levels in CATEGORICAL_LEVELS.items():
        value = record.get(name)
        try:
            value = int(value)
        except (TypeError, ValueError) as exc:
            raise RealDataError(f"categorical predictor {name}") from exc
        # Goal026's frozen vocabulary maps an unseen nominal level to an
        # all-zero indicator block; it is counted in the local diagnostics.
        vector.extend(float(value == level) for level in levels)
    output = np.asarray(vector, dtype=np.float32)
    if not np.isfinite(output).all():
        raise RealDataError("non-finite predictor")
    return output


def validate_auxiliary_records(
    records: Sequence[Mapping[str, Any]], target: str, held_fold: str,
) -> dict[str, Any]:
    """Validate the case-specific four-fold auxiliary eligibility view.

    This returns aggregate diagnostics for local binding metadata.  It never
    returns row membership, identifiers, coordinates, or response values.
    Pseudoabsences are deliberately excluded from the eligible view.
    """
    folds = {f"fold{i:02d}" for i in range(5)}
    if held_fold not in folds or not target:
        raise RealDataError("auxiliary case fold/target invalid")
    eligible: list[Mapping[str, Any]] = []
    unseen = {name: 0 for name in CATEGORICAL_PREDICTORS}
    for record in records:
        try:
            species = str(record["species"])
            fold = str(record["fold"])
            source = record["source"]
        except (KeyError, TypeError) as exc:
            raise RealDataError("auxiliary row schema") from exc
        if fold not in folds or source not in PROVENANCE:
            raise RealDataError("auxiliary row provenance/fold")
        if species == target or fold == held_fold or source == "pseudoabsence":
            continue
        eligible.append(record)
        for name, levels in CATEGORICAL_LEVELS.items():
            try:
                value = int(record[name])
            except (KeyError, TypeError, ValueError) as exc:
                raise RealDataError(f"auxiliary categorical predictor {name}") from exc
            unseen[name] += int(value not in levels)
    species_counts: dict[str, int] = {}
    for record in eligible:
        species = str(record["species"])
        species_counts[species] = species_counts.get(species, 0) + 1
    if len(species_counts) != 7 or any(count <= 0 for count in species_counts.values()):
        raise RealDataError("auxiliary species eligibility mismatch")
    equal_weight = 1.0 / 7.0
    return {
        "species_count": len(species_counts),
        "species_counts": dict(sorted(species_counts.items())),
        "fold_count": 4,
        "presence_rows": sum(record["source"] == "presence" for record in eligible),
        "survey_absence_rows": sum(record["source"] == "survey_supported_absence" for record in eligible),
        "pseudoabsence_rows": 0,
        "equal_species_weight": equal_weight,
        "species_weights": {name: equal_weight for name in sorted(species_counts)},
        "unseen_category_counts": unseen,
    }


def build_bundle_from_records(records: Sequence[Mapping[str, Any]], case: CaseSpec, *, strict_scope: bool = True) -> RealDataBundle:
    """Build a deidentified bundle from an already-authorised row view.

    ``records`` is intentionally a narrow boundary representation.  The real
    exporter converts the immutable Phase 1 RowSet/FeatureProvider into this
    representation and then drops all membership identifiers before writing.
    """
    if case.held_fold not in {f"fold{i:02d}" for i in range(5)} or case.target == "":
        raise RealDataError("case fold/target invalid")
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for source in records:
        try:
            species, cell, fold = str(source["species"]), str(source["cell"]), str(source["fold"])
            provenance = source["source"]
        except (KeyError, TypeError) as exc:
            raise RealDataError("row schema") from exc
        if provenance not in PROVENANCE or fold not in {f"fold{i:02d}" for i in range(5)}:
            raise RealDataError("row provenance/fold")
        key = (species, cell)
        if key in seen:
            raise RealDataError("duplicate species-cell")
        seen.add(key)
        label = 1.0 if provenance == "presence" else 0.0
        if source.get("y", label) != label:
            raise RealDataError("response provenance mismatch")
        rows.append({"species": species, "cell": cell, "fold": fold, "source": provenance, "y": label, "encoded": _encode(source)})
    rows.sort(key=lambda row: (row["species"], row["cell"]))
    if strict_scope:
        if len(rows) != 11039 or {row["species"] for row in rows} != set(REAL_SPECIES):
            raise RealDataError("outer-training scope mismatch")
        if {row["fold"] for row in rows} != {f"fold{i:02d}" for i in range(5)}:
            raise RealDataError("outer-training fold scope mismatch")
    if case.target not in {row["species"] for row in rows}:
        raise RealDataError("target missing")
    auxiliary_summary = validate_auxiliary_records(records, case.target, case.held_fold)
    target_rows = [row for row in rows if row["species"] == case.target]
    def matrix(predicate):
        selected = [row for row in target_rows if predicate(row)]
        if not selected:
            raise RealDataError("empty case role")
        return np.stack([row["encoded"] for row in selected]).astype(np.float32), np.asarray([row["y"] for row in selected], dtype=np.float32)
    held = case.held_fold
    stopping = case.stopping_fold
    x_discovery, y_discovery = matrix(lambda row: row["fold"] not in {held, stopping})
    x_stopping, y_stopping = matrix(lambda row: row["fold"] == stopping)
    x_replay, y_replay = matrix(lambda row: row["fold"] != held)
    x_assess, y_assess = matrix(lambda row: row["fold"] == held)
    aux = [row for row in rows if row["species"] != case.target and row["fold"] != case.held_fold and row["source"] in {"presence", "survey_supported_absence"}]
    aux_pseudoabsence_rows = sum(row["species"] != case.target and row["source"] == "pseudoabsence" for row in rows)
    target_pseudoabsence_rows = sum(row["species"] == case.target and row["source"] == "pseudoabsence" for row in rows)
    metadata = {
        "schema_version": "goal032-real-bundle-v1", "case_id": case.case_id, "target": case.target,
        "held_fold": held, "stopping_fold": stopping, "species_count": len({r["species"] for r in rows}),
        "outer_training_rows": len(rows), "predictor_count": 77, "feature_names_digest": _json_digest(FEATURE_NAMES),
        "auxiliary_species_count": len({r["species"] for r in aux}),
        "auxiliary_species_counts": {name: sum(r["species"] == name for r in aux) for name in sorted({r["species"] for r in aux})},
        "auxiliary_presence_rows": sum(r["source"] == "presence" for r in aux),
        "auxiliary_survey_absence_rows": sum(r["source"] == "survey_supported_absence" for r in aux),
        "auxiliary_pseudoabsence_rows": aux_pseudoabsence_rows,
        "target_pseudoabsence_rows": target_pseudoabsence_rows,
        "auxiliary_equal_species_weight": 1.0 / max(1, len({r["species"] for r in aux})),
        "auxiliary_summary": auxiliary_summary,
        "unseen_category_counts": dict(auxiliary_summary["unseen_category_counts"]),
        "source_binding_digest": _membership_digest(records),
        "role_counts": {},
    }
    metadata["role_counts"] = {"discovery": len(x_discovery), "stopping": len(x_stopping), "replay": len(x_replay), "inner_assessment": len(x_assess)}
    metadata["outer_attempted"] = 0
    metadata["outer_opened"] = 0
    metadata["auxiliary_aggregate_digest"] = _json_digest(auxiliary_summary)
    return RealDataBundle(case, x_discovery, y_discovery, x_stopping, y_stopping, x_replay, y_replay, x_assess, y_assess, metadata)


def bundle_digest(bundle: RealDataBundle) -> str:
    manifest = _portable_manifest(bundle)
    return _digest_manifest_and_arrays(manifest, _array_values(bundle))


def save_bundle(bundle: RealDataBundle, path: str | Path, config: Mapping[str, Any] | None = None) -> None:
    path = Path(path)
    metadata = _portable_manifest(bundle, config)
    metadata["bundle_digest"] = _digest_manifest_and_arrays(metadata, _array_values(bundle))
    payload = {f"x_{r}": getattr(bundle, f"x_{r}") for r in ROLES}
    # Held-fold labels are deliberately not exported.  The predictor array is
    # used only for an engineering digest during this canary.
    payload.update({f"y_{r}": getattr(bundle, f"y_{r}") for r in ROLES if r != "inner_assessment"})
    payload["x_held"] = payload.pop("x_inner_assessment")
    payload["metadata_json"] = np.frombuffer(json.dumps({"case": bundle.case.__dict__, "metadata": metadata}, sort_keys=True, separators=(",", ":")).encode(), dtype=np.uint8)
    np.savez_compressed(path, **payload)


def export_content_addressed_bundle(
    bundle: RealDataBundle, directory: str | Path, *, index_path: str | Path | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Write one content-addressed bundle and update a privacy-safe local index."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    digest = bundle_digest(bundle)
    path = directory / f"{bundle.case.case_id}-{digest}.npz"
    save_bundle(bundle, path)
    index_file = Path(index_path) if index_path is not None else directory / "index.json"
    index: dict[str, Any] = {}
    if index_file.is_file():
        try:
            loaded = json.loads(index_file.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                index = loaded
        except json.JSONDecodeError:
            raise RealDataError("local bundle index invalid")
    index[str(bundle.case.case_id)] = {"path": path.name, "bundle_digest": digest}
    index_file.write_text(json.dumps(index, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return path, index


def load_bundle(path: str | Path) -> RealDataBundle:
    try:
        with np.load(Path(path), allow_pickle=False) as payload:
            required = {f"x_{role}" for role in ROLES if role != "inner_assessment"} | {"x_held", "metadata_json"} | {f"y_{role}" for role in ROLES if role != "inner_assessment"}
            if set(payload.files) != required:
                raise RealDataError("bundle keys drift")
            envelope = json.loads(bytes(payload["metadata_json"].tolist()).decode())
            case = CaseSpec(**envelope["case"])
            metadata = envelope["metadata"]
            if set(metadata) != _MANIFEST_KEYS:
                raise RealDataError("bundle metadata allowlist mismatch")
            if metadata.get("schema_version") != "goal032-real-bundle-v2":
                raise RealDataError("bundle manifest schema mismatch")
            arrays = []
            for role in ROLES:
                x_value = payload["x_held" if role == "inner_assessment" else f"x_{role}"]
                if x_value.dtype != np.dtype("float32"):
                    raise RealDataError("bundle predictor dtype drift")
                y_value = np.zeros(len(x_value), dtype=np.float32) if role == "inner_assessment" else payload[f"y_{role}"]
                if y_value.dtype != np.dtype("float32"):
                    raise RealDataError("bundle response dtype drift")
                arrays.extend((np.asarray(x_value), np.asarray(y_value)))
            bundle = RealDataBundle(case, *arrays, metadata)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise RealDataError("invalid bundle") from exc
    claimed = bundle.metadata.get("bundle_digest")
    if claimed != _digest_manifest_and_arrays(bundle.metadata, _array_values(bundle)):
        raise RealDataError("bundle digest mismatch")
    return bundle


def validate_bundle(
    path: str | Path, expected: Mapping[str, Any], config: Mapping[str, Any] | None = None,
) -> RealDataBundle:
    if config is None and isinstance(expected.get("cases"), Sequence):
        config = expected
        case_id = expected.get("case_id")
        if case_id is not None:
            expected = next((row for row in expected["cases"] if row.get("case_id") == case_id), expected)
    bundle = load_bundle(path)
    manifest = dict(bundle.metadata)
    architecture = expected.get("architecture", {})
    architecture_id = architecture.get("id") if isinstance(architecture, Mapping) else architecture
    if bundle.case.case_id != expected.get("case_id") or bundle.case.architecture != architecture_id:
        raise RealDataError("bundle case identity mismatch")
    if expected.get("target") is not None and bundle.case.target != expected["target"]:
        raise RealDataError("bundle target identity mismatch")
    if expected.get("held_fold") is not None and bundle.case.held_fold != expected["held_fold"]:
        raise RealDataError("bundle held-fold identity mismatch")
    expected_stopping = expected.get("stopping_fold")
    if expected_stopping is not None and bundle.case.stopping_fold != expected_stopping:
        raise RealDataError("bundle stopping-fold identity mismatch")
    if "seed" in expected and bundle.case.seed != expected["seed"]:
        raise RealDataError("bundle seed identity mismatch")
    expected_base_seed = expected.get("base_seed")
    if expected_base_seed is None and config is not None:
        expected_base_seed = config.get("training", {}).get("base_seed")
    if expected_base_seed is None:
        expected_base_seed = bundle.case.seed
    if manifest.get("case_id") != bundle.case.case_id or manifest.get("goal_id") != "goal032-dsdm-real-compute-calibration" or manifest.get("target") != bundle.case.target or manifest.get("held_fold") != bundle.case.held_fold or manifest.get("stopping_fold") != bundle.case.stopping_fold or manifest.get("transform") != bundle.case.transform or manifest.get("architecture_id") != bundle.case.architecture or manifest.get("seed") != bundle.case.seed or manifest.get("base_seed") != expected_base_seed:
        raise RealDataError("bundle duplicated identity mismatch")
    if manifest.get("input_columns") != 77 or manifest.get("outer_attempted") != 0 or manifest.get("outer_opened") != 0:
        raise RealDataError("bundle manifest digest mismatch")
    expected_transform = expected.get("transform", f"cv_{expected.get('held_fold')}" if expected.get("held_fold") else None)
    if expected_transform is not None and manifest.get("transform") != expected_transform:
        raise RealDataError("bundle transform mismatch")
    expected_source = expected.get("source_binding_digest")
    if expected_source is not None and manifest.get("source_binding_digest") != expected_source:
        raise RealDataError("bundle source binding mismatch")
    expected_goal032 = expected.get("goal032_config_digest") or expected.get("config_digest")
    if expected_goal032 is None and config is not None:
        expected_goal032 = _config_digest(config)
    if expected_goal032 is not None and manifest.get("goal032_config_digest") != expected_goal032:
        raise RealDataError("bundle Goal032 config binding mismatch")
    bindings = expected.get("bindings", {}) if isinstance(expected, Mapping) else {}
    expected_authorities = expected.get("authority_digests")
    if expected_authorities is None and config is not None:
        expected_authorities = _authority_digests(config)
    if expected_authorities is None and isinstance(bindings, Mapping):
        names = ("goal029_config", "goal026_feature_contract", "goal026_fit_parameters")
        if all(isinstance(bindings.get(name), Mapping) for name in names):
            expected_authorities = {name: str(bindings[name].get("sha256")) for name in names}
    if expected_authorities is not None and manifest.get("authority_digests") != expected_authorities:
        raise RealDataError("bundle authority binding mismatch")
    arrays = _array_values(bundle)
    expected_shapes = manifest.get("array_shapes", {})
    for name, value in arrays.items():
        if expected_shapes.get(name) != list(value.shape):
            raise RealDataError("bundle shape manifest mismatch")
        claimed = manifest.get("array_digests", {}).get(name)
        if claimed != hashlib.sha256(value.tobytes(order="C")).hexdigest():
            raise RealDataError("bundle array digest mismatch")
    if manifest.get("bundle_digest") != _digest_manifest_and_arrays(manifest, arrays):
        raise RealDataError("bundle manifest digest mismatch")
    return bundle


def export_authorised_bundle(*args: Any, **kwargs: Any) -> RealDataBundle:
    """Lazy Phase 1 adapter; never imported by remote training modules."""
    if len(args) == 4 and not kwargs:
        return bind_case_from_foundation(*args)
    try:
        return bind_case_from_foundation(kwargs["root"], kwargs["config"], kwargs["case"], kwargs["output"])
    except KeyError as exc:
        raise RealDataError("authorised exporter requires root/config/case/output") from exc


def records_from_foundation(root: str | Path, config: Mapping[str, Any], case: CaseSpec | None = None) -> tuple[list[dict[str, Any]], Mapping[str, Any]]:
    """Materialise the narrow local serializer view from the sealed foundation."""
    from dsdm_phase1.goal029_production import ingest_production_foundation
    root = Path(root)
    verified: dict[str, Path] = {}
    bindings = config.get("bindings", {}) if isinstance(config, Mapping) else {}
    for name in ("goal029_config", "goal026_feature_contract", "goal026_fit_parameters"):
        binding = bindings.get(name)
        if not isinstance(binding, Mapping):
            raise RealDataError(f"{name} binding missing")
        path = root / str(binding.get("path", ""))
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != binding.get("sha256"):
            raise RealDataError(f"{name} binding digest mismatch")
        verified[name] = path
    foundation_config = config
    try:
        foundation_config = json.loads(verified["goal029_config"].read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RealDataError("Goal029 config invalid") from exc
    broker, provider, vault = ingest_production_foundation(root, foundation_config)
    if vault.attempted_open_count or vault.open_count:
        raise RealDataError("real outer access detected")
    rows = broker._rows  # sealed RowSet; this module is the sole local adapter
    records: list[dict[str, Any]] = []
    for key, pa, source in zip(rows.keys, rows.pa, rows.response_source):
        fold = broker._fold_by_key[key]
        transform_fold = case.held_fold if case is not None else fold
        try:
            value = provider._value(key, f"cv_{transform_fold}")
            continuous = value["continuous"]
            categorical = value["categorical"]
            record = {"species": key.species_id, "cell": key.grid_cell_id, "fold": fold, "y": float(pa), "source": source, "x": continuous}
            record.update(categorical)
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise RealDataError("foundation feature serialization failed") from exc
        records.append(record)
    return records, {
        "outer_attempted": vault.attempted_open_count,
        "outer_opened": vault.open_count,
        "source_binding_digest": _membership_digest(records),
        "goal032_config_digest": _config_digest(config, root),
        "authority_digests": _authority_digests(config),
        "base_seed": int(config.get("training", {}).get("base_seed", case.seed if case is not None else 31032)),
    }


def bind_case_from_foundation(root: str | Path, config: Mapping[str, Any], case: CaseSpec, output: str | Path) -> RealDataBundle:
    records, audit = records_from_foundation(root, config, case)
    bundle = build_bundle_from_records(records, case, strict_scope=True)
    metadata = dict(bundle.metadata)
    metadata.update(audit)
    bound = RealDataBundle(bundle.case, bundle.x_discovery, bundle.y_discovery, bundle.x_stopping, bundle.y_stopping, bundle.x_replay, bundle.y_replay, bundle.x_inner_assessment, bundle.y_inner_assessment, metadata)
    save_bundle(bound, output)
    return bound
