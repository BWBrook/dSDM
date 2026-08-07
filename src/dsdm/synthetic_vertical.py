"""Fixture, planner, sentinel runner, and receipt validator for Goal 031."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Sequence

import numpy as np
import torch

from .contracts import ExperimentContract, build_plan, load_contract
from .models import MultiHeadResidual, build_residual, clone_state, load_transfer
from .training import (
    Observation,
    copy_shared_trunk,
    derive_seed,
    fit_multihead_binary,
    fit_neural_binary,
    fit_q_linear,
    q_deep_scalar,
    scale_split,
    seed_everything,
    select_auxiliary,
)


class ReceiptError(ValueError):
    """Raised when aggregate evidence fails independent validation."""


class FixtureError(ValueError):
    """Raised before fitting when the synthetic observation contract drifts."""


@dataclass(frozen=True)
class SyntheticFixture:
    predictors: np.ndarray
    observations: tuple[Observation, ...]


@dataclass(frozen=True)
class SentinelResult:
    target_fits: int
    auxiliary_fits: int
    total_fits: int
    auxiliary_usable_count: int
    finite_output_fits: int
    method_fits: dict[str, int]
    architectures: tuple[str, ...]
    subset_sizes: tuple[int, ...]
    fixture_sha256: str
    execution_sha256: str


@dataclass(frozen=True)
class PreparedTarget:
    model: torch.nn.Module
    fit_seed: int
    freeze_trunk: bool


def prepare_target_model(
    *,
    spec,
    method: str,
    pooled: torch.nn.Module,
    multihead: MultiHeadResidual,
    target: str,
    fold: str,
    base_seed: int,
    endpoint: str,
    architecture: str,
) -> PreparedTarget:
    if method not in {
        "target_only_resmlp", "legacy_pooled_finetune",
        "multihead_frozen_trunk", "multihead_full_finetune",
        "target_plus_q_linear", "target_plus_q_deep",
    }:
        raise ValueError("unknown target method")
    input_dim = 29 if method in {"target_plus_q_linear", "target_plus_q_deep"} else 28
    initialization_seed = derive_seed(
        "target_initialization", target, fold, base_seed, endpoint, architecture
    )
    fit_seed = derive_seed("target_fit", target, fold, base_seed, endpoint, architecture)
    seed_everything(initialization_seed)
    model = build_residual(spec, input_dim, 1)
    freeze = False
    if method == "legacy_pooled_finetune":
        load_transfer(model, clone_state(pooled))
    elif method in {"multihead_frozen_trunk", "multihead_full_finetune"}:
        copy_shared_trunk(multihead, model)
        freeze = method == "multihead_frozen_trunk"
    return PreparedTarget(model=model, fit_seed=fit_seed, freeze_trunk=freeze)


def make_fixture(contract: ExperimentContract) -> SyntheticFixture:
    rng = np.random.default_rng(derive_seed(contract.raw["sentinel"]["seed"], "fixture"))
    predictors = rng.normal(size=(125, contract.predictor_count)).astype(np.float32)
    predictors[:, 0] += np.linspace(-1.5, 1.5, 125, dtype=np.float32)
    observations: list[Observation] = []
    for species in contract.species:
        for fold_index, fold in enumerate(contract.folds):
            cells = list(range(fold_index * 25, (fold_index + 1) * 25))
            cells.sort(key=lambda cell: derive_seed("provenance", species, fold, cell))
            assignments = (
                [("presence", 1.0)] * 8
                + [("survey_supported_absence", 0.0)] * 6
                + [("pseudoabsence", 0.0)] * 6
                + [("unknown", None)] * 5
            )
            for cell, (provenance, label) in zip(cells, assignments, strict=True):
                observations.append(
                    Observation(species, fold, provenance, label, predictors[cell].copy(), cell)
                )
    return SyntheticFixture(predictors, tuple(observations))


def summarize_fixture(fixture: SyntheticFixture) -> dict[str, object]:
    counts = Counter(row.provenance for row in fixture.observations)
    return {
        "cell_count": fixture.predictors.shape[0],
        "record_count": len(fixture.observations),
        "resolved_count": len(fixture.observations) - counts["unknown"],
        "unknown_count": counts["unknown"],
        "provenance_counts": {name: counts[name] for name in sorted(counts)},
    }


def fixture_sha256(contract: ExperimentContract, fixture: SyntheticFixture) -> str:
    digest = hashlib.sha256()
    digest.update(fixture.predictors.astype(np.float32, copy=False).tobytes())
    species_order = {name: index for index, name in enumerate(contract.species)}
    for row in sorted(fixture.observations, key=lambda item: (species_order.get(item.species, 999), item.cell_index)):
        digest.update(
            f"{row.species}|{row.cell_index}|{row.fold}|{row.provenance}|{row.label}".encode()
        )
    return digest.hexdigest()


def endpoint_rows(
    fixture: SyntheticFixture,
    target: str,
    held_fold: str,
    endpoint: str,
) -> tuple[Observation, ...]:
    available = [
        row for row in fixture.observations
        if row.species == target and row.fold != held_fold and row.label is not None
    ]
    if endpoint == "fraction100/full":
        return tuple(sorted(available, key=lambda row: row.cell_index))
    match = re.fullmatch(r"fraction(25|50)/ladder(00|01|02)", endpoint)
    if match is None:
        raise ValueError("invalid endpoint")
    fraction, ladder = match.groups()
    wanted = {
        "25": {"presence": 8, "survey_supported_absence": 6, "pseudoabsence": 6},
        "50": {"presence": 16, "survey_supported_absence": 12, "pseudoabsence": 12},
    }[fraction]
    selected: list[Observation] = []
    for provenance, count in wanted.items():
        candidates = [row for row in available if row.provenance == provenance]
        candidates.sort(
            key=lambda row: derive_seed("subset", target, held_fold, ladder, provenance, row.cell_index)
        )
        selected.extend(candidates[:count])
    return tuple(sorted(selected, key=lambda row: row.cell_index))


def validate_fixture(contract: ExperimentContract, fixture: SyntheticFixture) -> dict[str, object]:
    if fixture.predictors.shape != (125, 28) or fixture.predictors.dtype != np.float32:
        raise FixtureError("predictor shape or dtype drift")
    if not np.isfinite(fixture.predictors).all():
        raise FixtureError("non-finite predictor")
    if len(fixture.observations) != 1000:
        raise FixtureError("observation count drift")

    expected_pairs = {(species, cell) for species in contract.species for cell in range(125)}
    observed_pairs: list[tuple[str, int]] = []
    group_counts: dict[tuple[str, str], Counter] = {}
    label_for = {
        "presence": 1.0,
        "survey_supported_absence": 0.0,
        "pseudoabsence": 0.0,
        "unknown": None,
    }
    for row in fixture.observations:
        if row.species not in contract.species or row.fold not in contract.folds:
            raise FixtureError("species or fold drift")
        if not isinstance(row.cell_index, int) or not 0 <= row.cell_index < 125:
            raise FixtureError("cell range drift")
        if row.fold != contract.folds[row.cell_index // 25]:
            raise FixtureError("cell-to-fold drift")
        if row.provenance not in label_for or row.label != label_for[row.provenance]:
            raise FixtureError("provenance-label drift")
        if row.predictors.shape != (28,) or not np.isfinite(row.predictors).all():
            raise FixtureError("observation predictor drift")
        if not np.array_equal(row.predictors, fixture.predictors[row.cell_index]):
            raise FixtureError("observation predictor mismatch")
        observed_pairs.append((row.species, row.cell_index))
        group_counts.setdefault((row.species, row.fold), Counter())[row.provenance] += 1
    if len(set(observed_pairs)) != len(observed_pairs) or set(observed_pairs) != expected_pairs:
        raise FixtureError("duplicate or missing species-cell pair")
    expected_group = Counter({
        "presence": 8, "survey_supported_absence": 6,
        "pseudoabsence": 6, "unknown": 5,
    })
    if set(group_counts) != {(species, fold) for species in contract.species for fold in contract.folds}:
        raise FixtureError("species-fold coverage drift")
    if any(counts != expected_group for counts in group_counts.values()):
        raise FixtureError("per-fold provenance drift")

    expected_compositions = {
        "fraction25": Counter({"presence": 8, "survey_supported_absence": 6, "pseudoabsence": 6}),
        "fraction50": Counter({"presence": 16, "survey_supported_absence": 12, "pseudoabsence": 12}),
        "fraction100": Counter({"presence": 32, "survey_supported_absence": 24, "pseudoabsence": 24}),
    }
    for species in contract.species:
        for held_fold in contract.folds:
            full = endpoint_rows(fixture, species, held_fold, "fraction100/full")
            full_cells = {row.cell_index for row in full}
            if len(full) != 80 or Counter(row.provenance for row in full) != expected_compositions["fraction100"]:
                raise FixtureError("full endpoint composition drift")
            for ladder in ("00", "01", "02"):
                small = endpoint_rows(fixture, species, held_fold, f"fraction25/ladder{ladder}")
                medium = endpoint_rows(fixture, species, held_fold, f"fraction50/ladder{ladder}")
                small_cells = {row.cell_index for row in small}
                medium_cells = {row.cell_index for row in medium}
                if len(small) != 20 or Counter(row.provenance for row in small) != expected_compositions["fraction25"]:
                    raise FixtureError("25-percent endpoint composition drift")
                if len(medium) != 40 or Counter(row.provenance for row in medium) != expected_compositions["fraction50"]:
                    raise FixtureError("50-percent endpoint composition drift")
                if not small_cells < medium_cells or not medium_cells < full_cells:
                    raise FixtureError("endpoint nesting drift")
    return summarize_fixture(fixture)


def _architecture(contract: ExperimentContract, name: str):
    return next(item for item in contract.architectures if item.id == name)


def _tensor_rows(rows: Sequence[Observation], scaled: np.ndarray) -> tuple[torch.Tensor, torch.Tensor]:
    x = torch.tensor(np.stack([scaled[row.cell_index] for row in rows]), dtype=torch.float32)
    y = torch.tensor([row.label for row in rows], dtype=torch.float32)
    return x, y


def _update_model_digest(digest, tag: str, model: torch.nn.Module) -> None:
    digest.update(tag.encode())
    for name, value in sorted(model.state_dict().items()):
        digest.update(name.encode())
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())


def execute_sentinel(contract: ExperimentContract, fixture: SyntheticFixture) -> SentinelResult:
    validate_fixture(contract, fixture)
    sentinel = contract.raw["sentinel"]
    target = sentinel["target"]
    held_fold = sentinel["fold"]
    seed = sentinel["seed"]
    train_folds = set(contract.folds) - {held_fold}
    auxiliary_species = tuple(name for name in contract.species if name != target)
    auxiliary = select_auxiliary(fixture.observations, target, train_folds, auxiliary_species)
    if len(auxiliary) != 392 or Counter(row.species for row in auxiliary) != {name: 56 for name in auxiliary_species}:
        raise ValueError("auxiliary aggregate drift")

    train_cells = sorted({row.cell_index for row in fixture.observations if row.fold in train_folds})
    _, scaled, _ = scale_split(fixture.predictors[train_cells], fixture.predictors)
    aux_x, aux_y = _tensor_rows(auxiliary, scaled)
    aux_names = tuple(row.species for row in auxiliary)
    canonical = _architecture(contract, sentinel["canonical_architecture"])
    digest = hashlib.sha256()

    seed_everything(derive_seed(seed, "pooled_init"))
    pooled = build_residual(canonical, 28, 1)
    fit_neural_binary(
        pooled, aux_x, aux_y, canonical, derive_seed(seed, "pooled_fit"),
        species=aux_names, expected_species=auxiliary_species,
    )
    _update_model_digest(digest, "pooled", pooled)

    seed_everything(derive_seed(seed, "multihead_init"))
    multihead = MultiHeadResidual(canonical, 28, auxiliary_species)
    fit_multihead_binary(
        multihead, aux_x, aux_y, aux_names, auxiliary_species, canonical,
        derive_seed(seed, "multihead_fit"),
    )
    _update_model_digest(digest, "multihead", multihead)

    q_linear = fit_q_linear(
        aux_x.numpy(), aux_y.numpy(), seed,
        species=aux_names, expected_species=auxiliary_species,
    )
    digest.update(q_linear.coef_.tobytes())
    digest.update(q_linear.intercept_.tobytes())

    held = tuple(
        row for row in fixture.observations
        if row.species == target and row.fold == held_fold and row.label is not None
    )
    held_x, _ = _tensor_rows(held, scaled)
    executed_endpoints = {
        endpoint: endpoint_rows(fixture, target, held_fold, endpoint)
        for endpoint in sentinel["endpoints"]
    }
    subset_sizes = tuple(len(executed_endpoints[endpoint]) for endpoint in sentinel["endpoints"])
    method_fits = {method: 0 for method in contract.methods}
    target_fits = 0
    finite_output_fits = 0

    def run_target(method: str, endpoint: str, architecture_name: str) -> None:
        nonlocal target_fits, finite_output_fits
        spec = _architecture(contract, architecture_name)
        rows = executed_endpoints[endpoint]
        target_x, target_y = _tensor_rows(rows, scaled)
        apply_x = held_x

        if method == "target_plus_q_linear":
            train_q = q_linear.predict_proba(target_x.numpy())[:, 1].astype(np.float32)
            held_q = q_linear.predict_proba(held_x.numpy())[:, 1].astype(np.float32)
            target_x = torch.cat((target_x, torch.tensor(train_q[:, None])), dim=1)
            apply_x = torch.cat((held_x, torch.tensor(held_q[:, None])), dim=1)
        elif method == "target_plus_q_deep":
            target_x = torch.cat((target_x, q_deep_scalar(pooled, target_x)[:, None]), dim=1)
            apply_x = torch.cat((held_x, q_deep_scalar(pooled, held_x)[:, None]), dim=1)

        prepared = prepare_target_model(
            spec=spec, method=method, pooled=pooled, multihead=multihead,
            target=target, fold=held_fold, base_seed=seed, endpoint=endpoint,
            architecture=architecture_name,
        )
        model = prepared.model

        fit_neural_binary(
            model, target_x, target_y, spec, prepared.fit_seed,
            freeze_trunk=prepared.freeze_trunk,
        )
        model.eval()
        with torch.no_grad():
            finite = bool(torch.isfinite(model(apply_x)).all())
        if not finite:
            raise ValueError("non-finite sentinel output")
        _update_model_digest(digest, f"{method}|{endpoint}|{architecture_name}", model)
        target_fits += 1
        finite_output_fits += 1
        if architecture_name == sentinel["canonical_architecture"]:
            method_fits[method] += 1

    for endpoint in sentinel["endpoints"]:
        for method in contract.methods:
            run_target(method, endpoint, sentinel["canonical_architecture"])
    for architecture_name in sentinel["architectures"]:
        if architecture_name != sentinel["canonical_architecture"]:
            run_target("target_only_resmlp", sentinel["endpoints"][0], architecture_name)

    auxiliary_fits = 3
    total_fits = target_fits + auxiliary_fits
    if (target_fits, total_fits) != (sentinel["expected_target_fits"], sentinel["expected_total_fits"]):
        raise ValueError("sentinel fit count drift")
    return SentinelResult(
        target_fits=target_fits,
        auxiliary_fits=auxiliary_fits,
        total_fits=total_fits,
        auxiliary_usable_count=len(auxiliary),
        finite_output_fits=finite_output_fits,
        method_fits=method_fits,
        architectures=tuple(sentinel["architectures"]),
        subset_sizes=subset_sizes,
        fixture_sha256=fixture_sha256(contract, fixture),
        execution_sha256=digest.hexdigest(),
    )


def _canonical_bytes(payload: dict[str, object]) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _config_sha256(contract: ExperimentContract) -> str:
    return hashlib.sha256(contract.source_path.read_bytes()).hexdigest()


def _run_payload(
    contract: ExperimentContract,
    fixture: SyntheticFixture,
    result: SentinelResult,
) -> dict[str, object]:
    fixture_summary = validate_fixture(contract, fixture)
    actual_fixture_sha256 = fixture_sha256(contract, fixture)
    if result.fixture_sha256 != actual_fixture_sha256:
        raise ReceiptError("result-fixture digest mismatch")
    fixture_summary["sha256"] = actual_fixture_sha256
    sentinel = contract.raw["sentinel"]
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "goal_id": contract.raw["goal_id"],
        "status": "pass",
        "config_sha256": _config_sha256(contract),
        "contract": {
            "target_count": 8, "predictor_count": 28, "fold_count": 5,
            "endpoint_count": 7, "method_count": 6, "architecture_count": 24,
        },
        "planner": build_plan(contract),
        "fixture": fixture_summary,
        "sentinel": {
            "target": sentinel["target"], "fold": sentinel["fold"], "seed": sentinel["seed"],
            "endpoints": sentinel["endpoints"], "subset_sizes": list(result.subset_sizes),
            "auxiliary_usable_count": result.auxiliary_usable_count,
            "methods": result.method_fits, "architectures": list(result.architectures),
            "target_fits": result.target_fits, "auxiliary_fits": result.auxiliary_fits,
            "total_fits": result.total_fits, "finite_output_fits": result.finite_output_fits,
            "execution_sha256": result.execution_sha256,
        },
        "training": {
            "device": "cpu", "dtype": "float32", "torch_threads": 1,
            "deterministic_algorithms": True, "scaler_scope": "split_training_predictors_only",
            "loss": "BCEWithLogitsLoss", "batching": "full_batch", "epochs": 12,
            "optimizer": "AdamW", "learning_rate": 0.001, "scheduler": None,
            "early_stopping": False, "target_weighting": "unweighted",
            "auxiliary_weighting": "mean_of_within_species_means",
            "q_linear": {"penalty":"elasticnet","solver":"saga","C":1.0,"l1_ratio":0.5,"max_iter":2000,"tol":0.000001,"effective_threads":1},
            "randomization_pairing": {
                "seed_scope": "target_fold_base_seed_endpoint_architecture",
                "method_in_seed": False,
                "common_28_input_target_head": True,
                "common_multihead_frozen_full_initialization": True,
                "common_29_input_q_initialization": True,
                "legacy_replaces_full_pretrained_state": True,
            },
        },
        "outer_access": {"attempted": 0, "opened": 0},
        "checks": {"deterministic": True, "privacy": True},
    }
    payload["receipt_sha256"] = hashlib.sha256(_canonical_bytes(payload)).hexdigest()
    return payload


def write_run_receipt(
    contract: ExperimentContract,
    fixture: SyntheticFixture,
    result: SentinelResult,
    path: str | Path,
) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(_canonical_bytes(_run_payload(contract, fixture, result)))


_FORBIDDEN = re.compile(
    r"row.?id|cell.?id|grid.?cell|response.?label|prediction|species.?cell|/Users/|data/|tas_cam/|temp/|auc|tss|mcc|accuracy|performance|checkpoint|state_dict",
    re.IGNORECASE,
)


def validate_receipt(contract: ExperimentContract, path: str | Path) -> None:
    text = Path(path).read_text()
    if _FORBIDDEN.search(text):
        raise ReceiptError("privacy violation")
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ReceiptError("invalid receipt JSON") from exc
    if not isinstance(raw, dict) or set(raw) != {
        "schema_version", "goal_id", "status", "config_sha256", "contract",
        "planner", "fixture", "sentinel", "training", "outer_access", "checks",
        "receipt_sha256",
    }:
        raise ReceiptError("receipt schema drift")
    digest = raw.pop("receipt_sha256")
    if digest != hashlib.sha256(_canonical_bytes(raw)).hexdigest():
        raise ReceiptError("receipt digest drift")
    canonical_fixture = make_fixture(contract)
    canonical_fixture_summary = validate_fixture(contract, canonical_fixture)
    canonical_result = execute_sentinel(contract, canonical_fixture)
    canonical_fixture_summary["sha256"] = fixture_sha256(contract, canonical_fixture)
    expected = {
        "schema_version": "1.0",
        "goal_id": "goal031-dsdm-synthetic-vertical-slice",
        "status": "pass",
        "config_sha256": _config_sha256(contract),
        "contract": {
            "target_count": 8, "predictor_count": 28, "fold_count": 5,
            "endpoint_count": 7, "method_count": 6, "architecture_count": 24,
        },
        "planner": build_plan(contract),
        "fixture": canonical_fixture_summary,
        "sentinel": {
            "target": "sarcophilus_harrisii", "fold": "fold00", "seed": 31031,
            "endpoints": ["fraction25/ladder00", "fraction50/ladder00", "fraction100/full"],
            "subset_sizes": list(canonical_result.subset_sizes),
            "auxiliary_usable_count": canonical_result.auxiliary_usable_count,
            "methods": canonical_result.method_fits,
            "architectures": list(canonical_result.architectures),
            "target_fits": canonical_result.target_fits,
            "auxiliary_fits": canonical_result.auxiliary_fits,
            "total_fits": canonical_result.total_fits,
            "finite_output_fits": canonical_result.finite_output_fits,
            "execution_sha256": canonical_result.execution_sha256,
        },
        "training": {
            "device": "cpu", "dtype": "float32", "torch_threads": 1,
            "deterministic_algorithms": True,
            "scaler_scope": "split_training_predictors_only",
            "loss": "BCEWithLogitsLoss", "batching": "full_batch", "epochs": 12,
            "optimizer": "AdamW", "learning_rate": 0.001, "scheduler": None,
            "early_stopping": False, "target_weighting": "unweighted",
            "auxiliary_weighting": "mean_of_within_species_means",
            "q_linear": {
                "penalty": "elasticnet", "solver": "saga", "C": 1.0,
                "l1_ratio": 0.5, "max_iter": 2000, "tol": 0.000001,
                "effective_threads": 1,
            },
            "randomization_pairing": {
                "seed_scope": "target_fold_base_seed_endpoint_architecture",
                "method_in_seed": False,
                "common_28_input_target_head": True,
                "common_multihead_frozen_full_initialization": True,
                "common_29_input_q_initialization": True,
                "legacy_replaces_full_pretrained_state": True,
            },
        },
        "outer_access": {"attempted": 0, "opened": 0},
        "checks": {"deterministic": True, "privacy": True},
    }
    if raw != expected:
        raise ReceiptError("receipt semantic drift")


def _write_plan(contract: ExperimentContract, path: str | Path) -> None:
    payload = {
        "schema_version": "1.0", "goal_id": contract.raw["goal_id"], "kind": "plan",
        "fits_executed": 0, "planner": build_plan(contract),
        "outer_access": {"attempted": 0, "opened": 0},
    }
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(_canonical_bytes(payload))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    plan_parser = commands.add_parser("plan")
    plan_parser.add_argument("--output", required=True)
    run_parser = commands.add_parser("run")
    run_parser.add_argument("--output", required=True)
    validate_parser = commands.add_parser("validate")
    validate_parser.add_argument("--receipt", required=True)
    args = parser.parse_args(argv)
    contract = load_contract(args.config)
    if args.command == "plan":
        _write_plan(contract, args.output)
    elif args.command == "run":
        fixture = make_fixture(contract)
        write_run_receipt(contract, fixture, execute_sentinel(contract, fixture), args.output)
    else:
        validate_receipt(contract, args.receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
