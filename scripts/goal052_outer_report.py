"""Render a deterministic Markdown report from a closed Goal052 scores JSON.

This module is deliberately downstream of ``score_closed``.  It reads one
already-created score JSON and never opens responses, memberships, predictors,
or fitted artefacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "goal052-outer-scores-v1"
LEARNER_ARMS = (
    "target_only_random_init_resmlp",
    "target_plus_q_linear_resmlp",
    "multihead_frozen_trunk",
    "multihead_full_finetune",
    "selected_conventional",
    "selected_conventional_plus_q",
)
ARM_LABELS = {
    "target_only_random_init_resmlp": "Target only, random-init ResMLP",
    "target_plus_q_linear_resmlp": "Target + q linear ResMLP",
    "multihead_frozen_trunk": "Multihead, frozen trunk",
    "multihead_full_finetune": "Multihead, full fine-tune",
    "selected_conventional": "Goal051 selected conventional",
    "selected_conventional_plus_q": "Goal051 q-augmented conventional",
    "fixed_ensemble": "Fixed ensemble (AUC-only)",
}
REGISTERED_CONTRASTS = (
    "multihead_full_finetune_minus_target_only_random_init_resmlp",
    "multihead_full_finetune_minus_target_plus_q_linear_resmlp",
    "multihead_full_finetune_minus_goal051_selected_conventional",
    "multihead_full_finetune_minus_goal051_q_augmented_conventional",
    "multihead_frozen_trunk_minus_target_only_random_init_resmlp",
    "multihead_full_finetune_minus_multihead_frozen_trunk",
)
ENSEMBLE_CONTRASTS = (
    "fixed_ensemble_minus_multihead_full_finetune",
    "fixed_ensemble_minus_selected_conventional",
)
CONTRAST_LABELS = {
    "multihead_full_finetune_minus_target_only_random_init_resmlp": "Full fine-tune − target-only random-init ResMLP",
    "multihead_full_finetune_minus_target_plus_q_linear_resmlp": "Full fine-tune − target + q linear ResMLP",
    "multihead_full_finetune_minus_goal051_selected_conventional": "Full fine-tune − Goal051 selected conventional",
    "multihead_full_finetune_minus_goal051_q_augmented_conventional": "Full fine-tune − Goal051 q-augmented conventional",
    "multihead_frozen_trunk_minus_target_only_random_init_resmlp": "Frozen trunk − target-only random-init ResMLP",
    "multihead_full_finetune_minus_multihead_frozen_trunk": "Full fine-tune − frozen trunk",
    "fixed_ensemble_minus_multihead_full_finetune": "Fixed ensemble − full fine-tune",
    "fixed_ensemble_minus_selected_conventional": "Fixed ensemble − selected conventional",
}
METRIC_FIELDS = ("roc_auc", "tss", "balanced_accuracy", "mcc", "sensitivity", "specificity", "prevalence")
RICHNESS_BINS = ("10_24", "25_99", "100_plus")


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _nonempty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def validate_scores(payload: Mapping[str, Any]) -> None:
    """Check the report-facing score contract without inspecting raw data."""
    _mapping(payload, "scores")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported score schema: {payload.get('schema_version')!r}")
    for key in ("plan_digest", "closure_sha256", "response_provenance", "targets", "aggregate", "interpretive_limits"):
        if key not in payload:
            raise ValueError(f"scores missing required field: {key}")
    _nonempty_string(payload["plan_digest"], "plan_digest")
    _nonempty_string(payload["closure_sha256"], "closure_sha256")
    _mapping(payload["response_provenance"], "response_provenance")
    if not isinstance(payload["targets"], list):
        raise ValueError("targets must be an array")
    aggregate = _mapping(payload["aggregate"], "aggregate")
    for key in ("common73", "primary_by_region", "regional", "x20", "richness", "headline_decomposition", "matched_inner_attenuation"):
        if key not in aggregate:
            raise ValueError(f"aggregate missing required field: {key}")
    common = _mapping(aggregate["common73"], "aggregate.common73")
    if not _mapping(common.get("contrasts"), "aggregate.common73.contrasts"):
        raise ValueError("aggregate.common73.contrasts must be non-empty")
    if not _mapping(common.get("arm_metrics"), "aggregate.common73.arm_metrics"):
        raise ValueError("aggregate.common73.arm_metrics is required")
    for section_name in ("primary_by_region", "regional"):
        section = _mapping(aggregate[section_name], f"aggregate.{section_name}")
        if not section:
            raise ValueError(f"aggregate.{section_name} must be non-empty")
        for region, panel in section.items():
            panel = _mapping(panel, f"aggregate.{section_name}.{region}")
            if not _mapping(panel.get("contrasts"), f"aggregate.{section_name}.{region}.contrasts"):
                raise ValueError(f"aggregate.{section_name}.{region}.contrasts is required")
            if "target_count" not in panel:
                raise ValueError(f"aggregate.{section_name}.{region}.target_count is required")
    x20 = _mapping(aggregate["x20"], "aggregate.x20")
    for key in ("common_equal_region_macro", "common_three_region_intersection", "primary_by_region"):
        if key not in x20:
            raise ValueError(f"aggregate.x20 missing required field: {key}")
    richness = _mapping(aggregate["richness"], "aggregate.richness")
    for key in ("primary_by_region", "supplementary_three_region_macro"):
        if key not in richness:
            raise ValueError(f"aggregate.richness missing required field: {key}")
    if not isinstance(payload["interpretive_limits"], list):
        raise ValueError("interpretive_limits must be an array")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _number(value: Any) -> str:
    if value is None:
        return "NA"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (not math.isfinite(value)):
            return "NA"
        if float(value) == 0:
            return "0"
        return f"{value:.6g}"
    return str(value)


def _support_cell(stat: Mapping[str, Any] | None, total: Any = None) -> str:
    if not isinstance(stat, Mapping):
        return "NA"
    denominator = stat.get("denominator", stat.get("denom"))
    suffix = f" (n={denominator}" + (f"/{total})" if total is not None else ")") if denominator is not None else ""
    value = _number(stat.get("mean"))
    return f"{value}{suffix}"


def _stat_value(stat: Mapping[str, Any] | None, field: str, total: Any = None) -> str:
    if not isinstance(stat, Mapping):
        return "NA"
    denominator = stat.get("denominator", stat.get("denom"))
    suffix = f" (n={denominator}" + (f"/{total})" if total is not None else ")") if denominator is not None else ""
    return f"{_number(stat.get(field))}{suffix}"


def _positive(stat: Mapping[str, Any] | None, total: Any = None) -> str:
    if not isinstance(stat, Mapping):
        return "NA"
    denominator = stat.get("denominator", stat.get("denom"))
    if denominator is None:
        return "NA"
    suffix = f"/{total}" if total is not None else ""
    return f"{stat.get('positive_count', 'NA')}/{denominator}{suffix}"


def _contrast_names(aggregate: Mapping[str, Any]) -> list[str]:
    names = list(aggregate.get("contrasts", ()))
    if not names:
        names = list(_mapping(aggregate["common73"], "aggregate.common73")["contrasts"])
    required = [name for name in REGISTERED_CONTRASTS if name in names]
    if len(required) != len(REGISTERED_CONTRASTS):
        missing = [name for name in REGISTERED_CONTRASTS if name not in names]
        raise ValueError(f"registered contrasts missing from scores: {', '.join(missing)}")
    missing_ensemble = [name for name in ENSEMBLE_CONTRASTS if name not in names]
    if missing_ensemble:
        raise ValueError(f"fixed ensemble contrasts missing from scores: {', '.join(missing_ensemble)}")
    return required + list(ENSEMBLE_CONTRASTS)


def _table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(str(value).replace("|", "\\|") for value in row) + " |" for row in rows)
    return lines


def _contrast_table(panel: Mapping[str, Any], names: Sequence[str], *, title: str | None = None) -> list[str]:
    total = panel.get("target_count")
    rows = []
    contrasts = _mapping(panel.get("contrasts"), "panel.contrasts")
    for name in names:
        stat = contrasts.get(name)
        rows.append((CONTRAST_LABELS.get(name, name), _support_cell(stat, total), _stat_value(stat, "median", total), _positive(stat, total), stat.get("label", "NA") if isinstance(stat, Mapping) else "NA"))
    lines = []
    if title:
        lines.append(f"#### {title}")
        lines.append("")
    lines.extend(_table(("Contrast", "Mean (support)", "Median (support)", "Positive / denominator", "Descriptive label"), rows))
    return lines


def _absolute_table(panel: Mapping[str, Any]) -> list[str]:
    metrics = _mapping(_mapping(panel.get("arm_metrics"), "arm_metrics").get("absolute"), "arm_metrics.absolute")
    total = panel.get("target_count")
    rows = []
    for arm in (*LEARNER_ARMS, "fixed_ensemble"):
        cells = [ARM_LABELS[arm]]
        auc = _mapping(metrics.get("roc_auc", {}), "absolute.roc_auc").get(arm)
        cells.append(_stat_value(auc, "mean", total))
        for field in METRIC_FIELDS[1:]:
            if arm == "fixed_ensemble":
                cells.append("AUC-only")
            else:
                cells.append(_stat_value(_mapping(metrics.get(field, {}), f"absolute.{field}").get(arm), "mean", total))
        rows.append(cells)
    return _table(("Learner", "AUC", "TSS", "Balanced accuracy", "MCC", "Sensitivity", "Specificity", "Prevalence"), rows)


def _richness_table(richness_panel: Mapping[str, Any], composition: Mapping[str, Any], names: Sequence[str], *, macro: bool = False) -> list[str]:
    bins = _mapping(richness_panel.get("bins"), "richness bins")
    comp_bins = _mapping(composition.get("bins", {}), "background composition bins")
    total_targets = richness_panel.get("target_count", len(richness_panel.get("targets", [])))
    rows = []
    for label in RICHNESS_BINS:
        bin_item = _mapping(bins.get(label, {}), f"richness bin {label}")
        if macro:
            support_map = _mapping(bin_item.get("three_bin_common_support", {}), f"richness bin {label} common support")
            common_map = {name: support_map.get(name) for name in names}
            all_map = {name: _mapping(bin_item.get("contrasts", {}), f"richness bin {label}.contrasts").get(name) for name in names}
        else:
            common_map = _mapping(bin_item.get("common_support", {}), f"richness bin {label}.common_support")
            all_map = _mapping(bin_item.get("all_available", {}), f"richness bin {label}.all_available")
        composition_item = _mapping(comp_bins.get(label, {}), f"composition bin {label}")
        background = f"{composition_item.get('background_pairs', 'NA')} pairs; mean={_number(composition_item.get('mean_background_cells_per_target'))}; share={_number(composition_item.get('mean_target_share'))}"
        for name in names:
            common = common_map.get(name)
            available = all_map.get(name)
            rows.append((label, background, CONTRAST_LABELS.get(name, name), _support_cell(common, total_targets), _support_cell(available, total_targets)))
    return _table(("Bin", "Background count / share", "Contrast", "Common support mean", "All-available mean"), rows)


def _decomposition_table(decomposition: Mapping[str, Any], names: Sequence[str]) -> list[str]:
    rows = []
    for panel_kind, panels in decomposition.items():
        panel_map = _mapping(panels, f"headline_decomposition.{panel_kind}")
        for region, panel in panel_map.items():
            panel = _mapping(panel, f"headline_decomposition.{panel_kind}.{region}")
            contrasts = _mapping(panel.get("contrasts"), f"headline_decomposition.{panel_kind}.{region}.contrasts")
            for name in names:
                item = contrasts.get(name)
                item = item if isinstance(item, Mapping) else {}
                contributions = item.get("mean_weighted_bin_contributions")
                contributions = contributions if isinstance(contributions, Mapping) else {}
                rows.append((
                    panel_kind.replace("_", " "), region, CONTRAST_LABELS.get(name, name),
                    _number(contributions.get("10_24")),
                    _number(contributions.get("25_99")),
                    _number(contributions.get("100_plus")),
                    _number(item.get("sum")), _number(item.get("absolute_error")),
                ))
    return _table(("Panel", "Region", "Contrast", "10–24 contribution", "25–99 contribution", "100+ contribution", "Sum", "Absolute error"), rows)


def _attenuation_rows(attenuation: Mapping[str, Any], names: Sequence[str]):
    """Yield flat rows from the scorer's common and nested regional panels."""
    for panel_name, panel in attenuation.items():
        if not isinstance(panel, Mapping):
            continue  # scorer's non-tabular ``reference`` field
        if panel_name in ("primary_by_region", "regional"):
            for region, regional_panel in panel.items():
                yield f"{panel_name.replace('_', ' ')} / {region}", regional_panel, names
        else:
            yield ("common73 equal-region macro" if panel_name == "common_equal_region_macro" else panel_name.replace("_", " ")), panel, names


def render_report(payload: Mapping[str, Any], *, source_sha256: str) -> str:
    """Render one scores object; ``source_sha256`` is the exact JSON-file hash."""
    validate_scores(payload)
    aggregate = _mapping(payload["aggregate"], "aggregate")
    names = _contrast_names(aggregate)
    registered = [name for name in names if name in REGISTERED_CONTRASTS]
    common = _mapping(aggregate["common73"], "aggregate.common73")
    lines = [
        "# Goal052 retained-full outer assessment",
        "",
        "This report is a deterministic rendering of an already-created `goal052-outer-scores-v1` JSON. It contains descriptive outer discrimination summaries only; it does not establish inferential significance, occupancy, or ecological/observation mechanisms.",
        "",
        "## Source identity",
        "",
        f"- Score JSON SHA256: `{source_sha256}`",
        f"- Plan digest: `{payload['plan_digest']}`",
        f"- Closure SHA256: `{payload['closure_sha256']}`",
        f"- Score schema: `{payload['schema_version']}`",
        f"- Created UTC: `{payload.get('created_utc', 'NA')}`",
        "",
        "## Interpretation and support",
        "",
        "Means and medians are equal-target summaries of the supplied score JSON. Every numeric cell carries its evaluated denominator; `NA` is retained when the source has no reportable value. The fixed ensemble is a fixed 50:50 probability average and is AUC-only and exploratory; no threshold metrics are assigned to it.",
        "",
        "## Primary common73 panel",
        "",
        f"Panel target count: `{common.get('target_count', 'NA')}`; equal-region macro means are target-wise means of the supplied regional contrasts.",
        "",
    ]
    lines.extend(_contrast_table(common, registered))
    lines.extend(["", "## Primary contrasts by region", ""])
    for region, panel in _mapping(aggregate["primary_by_region"], "primary_by_region").items():
        lines.append(f"### {region} (primary panel; target count {panel.get('target_count', 'NA')})")
        lines.append("")
        lines.extend(_contrast_table(panel, registered))
        lines.append("")
    ensemble = [name for name in names if name in ENSEMBLE_CONTRASTS]
    lines.extend(["## Fixed ensemble diagnostic contrasts", "", "These registered ensemble contrasts are exploratory AUC diagnostics. The fixed ensemble has no threshold metrics and these differences do not support inferential or mechanistic claims.", ""])
    lines.extend(_contrast_table(common, ensemble, title="Common73"))
    lines.append("")
    for region, panel in _mapping(aggregate["primary_by_region"], "primary_by_region").items():
        lines.extend(_contrast_table(panel, ensemble, title=f"{region} primary panel"))
        lines.append("")
    lines.extend(["## Absolute learner performance on common73", "", "AUC is shown for all six learners and the fixed ensemble. TSS, balanced accuracy, MCC, sensitivity, specificity, and prevalence use the frozen fixed thresholds and are shown for the six learners only. Support is `evaluated / panel target count`.", ""])
    lines.extend(_absolute_table(common))
    lines.extend(["", "## Secondary regional panels", "", "These panels retain their exact supplied membership counts; their denominators are not substituted with the common73 count.", ""])
    for region, panel in _mapping(aggregate["regional"], "regional").items():
        lines.append(f"### {region} (target count {panel.get('target_count', 'NA')})")
        lines.append("")
        lines.extend(_contrast_table(panel, registered))
        lines.append("")
    x20 = _mapping(aggregate["x20"], "x20")
    macro = _mapping(x20["common_equal_region_macro"], "x20.common_equal_region_macro")
    lines.extend(["## X20 sensitivity panel", "", "The main X20 macro gives each region equal weight after using its own eligible target denominator (the expected pattern is 72/73/73). The three-region common intersection is supplementary and is reported separately.", ""])
    macro_rows = []
    macro_contrasts = _mapping(macro.get("contrasts"), "x20 macro contrasts")
    for name in registered:
        stat = macro_contrasts.get(name, {})
        regional_means = _mapping(stat.get("regional_means", {}), f"x20 {name} regional means")
        denominators = _mapping(stat.get("regional_denominators", {}), f"x20 {name} regional denominators")
        macro_rows.append((CONTRAST_LABELS[name], _number(stat.get("mean")), *[f"{_number(regional_means.get(region))} (n={denominators.get(region, 'NA')})" for region in ("NCP", "SEH", "NNC")]))
    lines.extend(_table(("Contrast", "Equal-region macro", "NCP", "SEH", "NNC"), macro_rows))
    lines.extend(["", "### Supplementary common three-region intersection", ""])
    intersection = _mapping(x20["common_three_region_intersection"], "x20 common intersection")
    lines.append(f"Regions: `{', '.join(map(str, intersection.get('regions', [])))}`; target count: `{intersection.get('target_count', 'NA')}`. These values use the common intersection and are supplementary to the main region-specific macro.")
    lines.append("")
    lines.extend(_contrast_table(intersection, registered))
    lines.extend(["", "## Recorded-richness diagnostics", "", "Background counts are target-background pairs. Shares are mean target shares for the equally weighted target panel. Common support requires all three richness bins for the contrast; all-available support uses each bin's available targets. These are descriptive diagnostics of the retained-inner discovery prospect and do not identify ecological versus observation mechanisms.", ""])
    richness = _mapping(aggregate["richness"], "richness")
    primary_composition = _mapping(aggregate.get("primary_background_composition", {}), "primary_background_composition")
    for region, panel in _mapping(richness["primary_by_region"], "richness.primary_by_region").items():
        lines.append(f"### {region} primary panel")
        lines.append("")
        lines.extend(_richness_table(panel, primary_composition.get(region, {}), names))
        lines.append("")
    lines.extend(["### Supplementary three-region macro", ""])
    lines.extend(_richness_table(_mapping(richness["supplementary_three_region_macro"], "richness supplementary macro"), {}, names, macro=True))
    lines.extend(["", "## Headline decomposition", "", "These are the scorer's mechanical equal-target decomposition terms, including sparse richness bins. They are arithmetic diagnostics rather than separate reportable bin AUC claims.", ""])
    lines.extend(_decomposition_table(_mapping(aggregate["headline_decomposition"], "headline_decomposition"), names))
    lines.extend(["", "## Matched inner attenuation", "", "Outer-minus-inner differences compare the supplied outer contrasts with the accepted matched inner target100/full differences. They are descriptive attenuation summaries, not recalibration or causal effects.", ""])
    attenuation = _mapping(aggregate["matched_inner_attenuation"], "matched_inner_attenuation")
    attenuation_rows = []
    for label, panel, panel_names in _attenuation_rows(attenuation, registered):
        panel = panel if isinstance(panel, Mapping) else {}
        for name in panel_names:
            item = panel.get(name)
            item = item if isinstance(item, Mapping) else {}
            attenuation_rows.append((label, CONTRAST_LABELS[name], _number(item.get("inner_mean_difference")), _number(item.get("outer_mean_difference")), _number(item.get("outer_minus_inner")), item.get("target_count", "NA")))
    lines.extend(_table(("Panel", "Contrast", "Inner mean", "Outer mean", "Outer − inner", "Targets"), attenuation_rows))
    lines.extend(["", "## Interpretive limits", ""])
    for limit in payload["interpretive_limits"]:
        lines.append(f"- {limit}")
    lines.extend(["", "## Provenance note", "", "This renderer preserves the score JSON's plan and closure identity in the report. It performs no fitting, response loading, threshold selection, recalculation, or data filtering.", ""])
    return "\n".join(lines)


def render_scores_file(scores_path: Path, output_path: Path) -> str:
    """Read one score JSON and write a report without overwriting other content."""
    scores_path = Path(scores_path)
    output_path = Path(output_path)
    raw = scores_path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    report = render_report(payload, source_sha256=sha256_bytes(raw))
    if output_path.exists():
        existing = output_path.read_text(encoding="utf-8")
        if existing != report:
            raise FileExistsError(f"refusing to overwrite different report: {output_path}")
        return report
    output_path.write_text(report, encoding="utf-8")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scores_json", type=Path, help="already-created goal052-outer-scores-v1 JSON")
    parser.add_argument("output_md", type=Path, help="named Markdown report path")
    args = parser.parse_args(argv)
    render_scores_file(args.scores_json, args.output_md)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
