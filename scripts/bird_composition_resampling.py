"""Report the fixed bird species-composition resampling ranges.

This is a reporting-only calculation over accepted aggregate AUC summaries and
the response-free focal-block map.  It does not open response data, fit models,
or rescore predictions.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "docs/plan/BirdCompositionResampling-20261008.md"
SUMMARY_PATH = ROOT / "evidence/cross_case_synthesis/20261005/revision-01/summary.json"
CROSSFIT_PATH = ROOT / "data/processed/dsdm/goal050-seawfb-modeling-foundation/crossfit_plan.json"
DEFAULT_OUTPUT_DIR = ROOT / "evidence/cross_case_synthesis/20261008"

PLAN_SHA256 = "68602df74c8e1c52326644a6a60c73f31ec5ebed7c52662ca4740fec2cd4f904"
SUMMARY_SHA256 = "6834e34c74767864686862734f57a64a2ac10b324fcdadab89797e1cecbe0fd2"
CROSSFIT_SHA256 = "b3abdb006fb7d384445db376d5ba3f0f7b48afd170982494f88ff20ef612e804"

REPLICATES = 100_000
BATCH_SIZE = 4096
SPECIES_COUNT = 73
BLOCK_COUNT = 10
BLOCK_IDS = tuple(range(BLOCK_COUNT))
EXPECTED_BLOCK_COUNTS = (6, 4, 3, 9, 7, 8, 9, 10, 7, 10)
REGIONS = ("NCP", "SEH", "NNC")
COMPARATORS = ("target_only", "conventional")
METHODS = ("fine_tuned", "target_only", "conventional")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _finite(value: object, label: str) -> float:
    result = float(value)
    require(np.isfinite(result), f"non-finite AUC: {label}")
    return result


def validate_primary_inventory(
    species: Sequence[str],
    focal_blocks: Mapping[str, int],
    expected_counts: Sequence[int] = EXPECTED_BLOCK_COUNTS,
) -> dict[str, object]:
    """Validate the canonical panel and return its block inventory."""

    names = tuple(species)
    require(len(names) == SPECIES_COUNT, f"expected {SPECIES_COUNT} species")
    require(names == tuple(sorted(names)), "species must be in ascending lexical order")
    require(len(set(names)) == SPECIES_COUNT, "species are not unique")
    missing = sorted(set(names) - set(focal_blocks))
    require(not missing, f"focal block mapping missing species: {missing}")
    mapped = [int(focal_blocks[name]) for name in names]
    require(all(block in BLOCK_IDS for block in mapped), "focal block ID outside 0..9")
    counts = tuple(mapped.count(block) for block in BLOCK_IDS)
    require(counts == tuple(expected_counts), f"focal block counts changed: {counts}")
    return {
        "n_species": len(names),
        "n_blocks": len(BLOCK_IDS),
        "species": list(names),
        "block_ids": list(BLOCK_IDS),
        "block_counts": list(counts),
    }


def _matrix_from_cases(summary: Mapping[str, object]) -> tuple[list[str], dict[str, np.ndarray], dict[str, object]]:
    """Extract paired inner and equal-region outer contrasts from the aggregate."""

    cases = summary.get("cases")
    require(isinstance(cases, Mapping), "aggregate summary cases missing")

    def rows(case: str) -> dict[str, Mapping[str, object]]:
        value = cases.get(case)
        require(isinstance(value, Mapping), f"aggregate case missing: {case}")
        records = value.get("species")
        require(isinstance(records, list), f"aggregate species rows missing: {case}")
        result: dict[str, Mapping[str, object]] = {}
        for record in records:
            require(isinstance(record, Mapping), f"aggregate row is not an object: {case}")
            name = record.get("species")
            require(isinstance(name, str) and name not in result, f"invalid species row: {case}")
            require(set(record) == {"species", *METHODS}, f"aggregate row schema drift: {case}")
            result[name] = record
        return result

    inner = rows("birds_inner")
    primary = sorted(inner)
    require(len(primary) == SPECIES_COUNT, "inner panel is not 73 species")
    require(tuple(primary) == tuple(sorted(primary)), "inner species are not lexical")
    regional = {region: rows(f"birds_{region}") for region in REGIONS}
    require(all(set(value) == set(primary) for value in regional.values()), "regional species sets differ")
    accepted_outer = rows("birds_outer")
    require(set(accepted_outer) == set(primary), "accepted equal-region species set differs")

    contrasts: dict[str, np.ndarray] = {}
    inner_values = {method: np.array([_finite(inner[name][method], f"birds_inner/{name}/{method}") for name in primary]) for method in METHODS}
    contrasts["birds_inner"] = {comparator: inner_values["fine_tuned"] - inner_values[comparator] for comparator in COMPARATORS}  # type: ignore[assignment]

    outer_values = {
        method: np.array(
            [
                np.mean([_finite(regional[region][name][method], f"birds_{region}/{name}/{method}") for region in REGIONS])
                for name in primary
            ]
        )
        for method in METHODS
    }
    accepted_outer_values = {
        method: np.array([_finite(accepted_outer[name][method], f"birds_outer/{name}/{method}") for name in primary])
        for method in METHODS
    }
    require(np.allclose(outer_values["fine_tuned"], accepted_outer_values["fine_tuned"], rtol=0, atol=2e-15), "equal-region fine-tuned values drift")
    require(np.allclose(outer_values["target_only"], accepted_outer_values["target_only"], rtol=0, atol=2e-15), "equal-region target-only values drift")
    require(np.allclose(outer_values["conventional"], accepted_outer_values["conventional"], rtol=0, atol=2e-15), "equal-region conventional values drift")
    contrasts["birds_outer"] = {comparator: outer_values["fine_tuned"] - outer_values[comparator] for comparator in COMPARATORS}  # type: ignore[assignment]
    return primary, contrasts, {"inner": inner_values, "outer": outer_values, "accepted_outer": accepted_outer_values}


def species_resampling_replicates(
    contrasts: Mapping[str, np.ndarray],
    rng: np.random.Generator,
    replicates: int = REPLICATES,
    batch_size: int = BATCH_SIZE,
) -> dict[str, np.ndarray]:
    """Return jointly sampled species means for each comparator.

    One species-index draw is reused for every comparator.  The temporary
    index and mean arrays are bounded by ``batch_size`` and are never written
    to an evidence file.
    """

    require(contrasts, "no contrasts supplied")
    names = tuple(contrasts)
    arrays = {name: np.asarray(contrasts[name], dtype=float) for name in names}
    lengths = {len(values) for values in arrays.values()}
    require(lengths == {SPECIES_COUNT}, "species contrast inventory is not 73")
    require(replicates > 0 and batch_size > 0, "replicates and batch size must be positive")
    output = {name: np.empty(replicates, dtype=float) for name in names}
    for start in range(0, replicates, batch_size):
        stop = min(start + batch_size, replicates)
        indices = rng.integers(0, SPECIES_COUNT, size=(stop - start, SPECIES_COUNT))
        for name, values in arrays.items():
            output[name][start:stop] = values[indices].mean(axis=1)
    return output


def focal_block_resampling_replicates(
    contrasts: Mapping[str, np.ndarray],
    block_by_species: Sequence[int],
    rng: np.random.Generator,
    replicates: int = REPLICATES,
    batch_size: int = BATCH_SIZE,
) -> dict[str, np.ndarray]:
    """Return jointly sampled focal-block ratio-of-sums means."""

    mapping = np.asarray(block_by_species, dtype=int)
    require(mapping.ndim == 1 and mapping.size > 0, "focal block species inventory is empty")
    block_ids = tuple(sorted(set(mapping.tolist())))
    require(block_ids == tuple(range(len(block_ids))), "focal block IDs must be contiguous from zero")
    arrays = {name: np.asarray(contrasts[name], dtype=float) for name in contrasts}
    require(all(values.shape == mapping.shape for values in arrays.values()), "block contrast inventory does not match mapping")
    n_blocks = len(block_ids)
    block_counts = np.bincount(mapping, minlength=n_blocks).astype(float)
    block_sums = {name: np.bincount(mapping, weights=values, minlength=n_blocks) for name, values in arrays.items()}
    output = {name: np.empty(replicates, dtype=float) for name in arrays}
    for start in range(0, replicates, batch_size):
        stop = min(start + batch_size, replicates)
        draws = rng.integers(0, n_blocks, size=(stop - start, n_blocks))
        denominator = block_counts[draws].sum(axis=1)
        for name, sums in block_sums.items():
            output[name][start:stop] = sums[draws].sum(axis=1) / denominator
    return output


def one_copy_focal_block_mean(values: np.ndarray, block_by_species: Sequence[int]) -> float:
    """Calculate the ratio-of-sums mean when every focal block is copied once."""

    array = np.asarray(values, dtype=float)
    mapping = np.asarray(block_by_species, dtype=int)
    require(array.ndim == 1 and array.shape == mapping.shape and array.size > 0, "one-copy inventory is empty or mismatched")
    n_blocks = int(mapping.max()) + 1
    require(np.array_equal(np.unique(mapping), np.arange(n_blocks)), "one-copy block IDs must be contiguous from zero")
    counts = np.bincount(mapping, minlength=n_blocks)
    sums = np.bincount(mapping, weights=array, minlength=n_blocks)
    return float(sums.sum() / counts.sum())


def _summary_record(case: str, comparator: str, scheme: str, observed: float, sampled: np.ndarray, n_blocks: int | None) -> dict[str, object]:
    lower, upper = np.quantile(sampled, [0.025, 0.975], method="linear")
    return {
        "case": case,
        "comparator": comparator,
        "scheme": scheme,
        "n_species": SPECIES_COUNT,
        "n_blocks": n_blocks,
        "mean": float(observed),
        "lower": float(lower),
        "upper": float(upper),
        "width": float(upper - lower),
    }


def _rng_metadata(children: Sequence[np.random.SeedSequence]) -> dict[str, object]:
    return {
        "seed": 20261008,
        "bit_generator": "PCG64",
        "numpy_version": np.__version__,
        "python_version": platform.python_version(),
        "replicates": REPLICATES,
        "batch_size": BATCH_SIZE,
        "quantile_method": "linear",
        "streams": [{"stream": index, "spawn_key": list(child.spawn_key), "entropy": child.entropy} for index, child in enumerate(children)],
    }


def run(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, object]:
    """Generate the deterministic JSON and CSV evidence outputs."""

    require(sha256(PLAN_PATH) == PLAN_SHA256, "resampling plan changed")
    require(sha256(SUMMARY_PATH) == SUMMARY_SHA256, "accepted aggregate summary changed")
    require(sha256(CROSSFIT_PATH) == CROSSFIT_SHA256, "crossfit plan changed")
    summary = json.loads(SUMMARY_PATH.read_text())
    crossfit = json.loads(CROSSFIT_PATH.read_text())
    require(summary.get("schema_version") == "dsdm-cross-case-synthesis-v2", "aggregate schema drift")
    require(crossfit.get("schema_version") == "goal050-crossfit-v1", "crossfit schema drift")
    primary, contrasts, _ = _matrix_from_cases(summary)
    focal_map = crossfit.get("focal_blocks")
    require(isinstance(focal_map, Mapping), "focal block mapping missing")
    inventory = validate_primary_inventory(primary, focal_map)
    block_by_species = [int(focal_map[name]) for name in primary]

    # These checks deliberately precede construction of either resampling
    # stream.  They bind the reported observed means and the one-copy block
    # calculation to the accepted unsampled aggregate first.
    observed_means: dict[str, dict[str, float]] = {}
    accepted_mean_checks: dict[str, dict[str, bool]] = {}
    one_copy_checks: dict[str, bool] = {}
    for case in ("birds_inner", "birds_outer"):
        observed_means[case] = {}
        accepted_mean_checks[case] = {}
        accepted_contrasts = summary["cases"][case]["contrasts"]
        for comparator in COMPARATORS:
            observed = float(np.mean(contrasts[case][comparator]))
            accepted = float(accepted_contrasts[comparator]["mean"])
            observed_means[case][comparator] = observed
            accepted_mean_checks[case][comparator] = bool(np.isclose(observed, accepted, rtol=0, atol=2e-15))
    for comparator in COMPARATORS:
        one_copy_checks[comparator] = bool(
            np.isclose(
                one_copy_focal_block_mean(contrasts["birds_inner"][comparator], block_by_species),
                observed_means["birds_inner"][comparator],
                rtol=0,
                atol=2e-15,
            )
        )
    require(all(all(checks.values()) for checks in accepted_mean_checks.values()), "accepted unsampled mean mismatch")
    require(all(one_copy_checks.values()), "one-copy focal-block mean mismatch")

    before_resampling = {
        "accepted_unsampled_means": accepted_mean_checks,
        "one_copy_focal_block_reproduces_inner_mean": one_copy_checks,
    }
    children = np.random.SeedSequence(20261008).spawn(2)
    species_rng = np.random.Generator(np.random.PCG64(children[0]))
    block_rng = np.random.Generator(np.random.PCG64(children[1]))
    records: list[dict[str, object]] = []
    joint_contrasts = {
        f"{case}/{comparator}": contrasts[case][comparator]
        for case in ("birds_inner", "birds_outer")
        for comparator in COMPARATORS
    }
    joint_sampled = species_resampling_replicates(joint_contrasts, species_rng)
    for case in ("birds_inner", "birds_outer"):
        for comparator in COMPARATORS:
            records.append(_summary_record(case, comparator, "species", observed_means[case][comparator], joint_sampled[f"{case}/{comparator}"], None))

    block_sampled = focal_block_resampling_replicates(contrasts["birds_inner"], block_by_species, block_rng)
    for comparator in COMPARATORS:
        records.append(
            _summary_record(
                "birds_inner", comparator, "focal_block", observed_means["birds_inner"][comparator], block_sampled[comparator], BLOCK_COUNT
            )
        )

    invariant_checks = {
        "plan_hash": True,
        "summary_hash": True,
        "crossfit_hash": True,
        "panel_species_sets_identical": True,
        "finite_auc_values": True,
        "equal_region_reproduces_accepted_outer": True,
        "focal_block_mapping_complete": True,
        "focal_block_counts": list(inventory["block_counts"]),
        "accepted_unsampled_means": accepted_mean_checks,
        "one_copy_focal_block_reproduces_inner_mean": one_copy_checks,
        "before_resampling": before_resampling,
        "paired_comparators_share_species_draws": True,
        "response_data_opened": False,
        "model_fits_run": False,
    }
    output: dict[str, object] = {
        "schema_version": "bird-composition-resampling-v1",
        "analysis": "central 95% species-composition resampling range",
        "plan": {"path": str(PLAN_PATH.relative_to(ROOT)), "sha256": PLAN_SHA256},
        "source": {"path": str(SUMMARY_PATH.relative_to(ROOT)), "sha256": SUMMARY_SHA256},
        "script": {"path": str(Path(__file__).resolve().relative_to(ROOT)), "sha256": sha256(Path(__file__).resolve())},
        "inputs": {"crossfit_plan": {"path": str(CROSSFIT_PATH.relative_to(ROOT)), "sha256": CROSSFIT_SHA256}},
        "accepted_summary_inputs": summary["inputs"],
        "rng": _rng_metadata(children),
        "canonical_panel": inventory,
        "observed_means": observed_means,
        "records": records,
        "invariant_checks": invariant_checks,
        "limits": [
            "The 73 species were selected for support and are not exchangeable random draws from a defined species population.",
            "These ranges describe empirical reweighting of the observed panel; they are not confidence intervals or population, fitting, spatial-sampling, model-selection, or ecological-replicate uncertainty.",
            "Focal blocks share block-specific pretrained objects and are neither spatial nor taxonomic clusters.",
            "Focal-block resampling does not capture dependence from common folds, predictors, architecture selection, geography, or overlapping auxiliary pools.",
            "Ten focal blocks provide limited tail resolution; neither scheme is selected as a conservative inferential interval.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "bird-composition-resampling.json").write_text(json.dumps(output, sort_keys=True, indent=2) + "\n")
    fields = ["case", "comparator", "scheme", "n_species", "n_blocks", "mean", "lower", "upper", "width"]
    with (output_dir / "bird-composition-resampling.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="output directory (used for deterministic scratch reruns)")
    args = parser.parse_args()
    result = run(args.output_dir.resolve())
    for record in result["records"]:
        print(json.dumps(record, sort_keys=True))


if __name__ == "__main__":
    main()
