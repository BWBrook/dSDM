# Outer assessment review, 5 October 2026

These files certify and summarize one completed assessment. They do not launch
fits or select models. The immutable score SHA256 is
`3a81b166f95551afc199577b86c200bf8cc6f91a24289ec5ad5583a9421f4a41`.

| Evidence | Scope |
|---|---|
| `return-review.json` | Local rehash of 185 returned files, 26 controller files and 29 frozen sources |
| `return-complete-006.json` | Successful return-only reconciliation of the preserved report polling failure |
| `return-source-006.py` | Exact operational source used for that return; **do not rerun** completed controls |
| `native-report.md` | Byte-identical copy of the successful frozen report |
| `aggregate-check.py` / `.json` | All 471 target-region rows, frozen panels/thresholds and eight aggregate X10/X20 contrasts; 232 numerical comparisons |
| `richness-check.py` / `.json` | All-target richness support, summaries, weighted identities and matched-inner attenuation; 33,854 checked invariants |
| `independent-score-check.py` / `.json` | Independent response/richness reconstruction, tied-rank AUC and fixed-threshold metrics on three prospective species across all regions and X10/X20; 2,268 field comparisons |
| `diagnostics-extract.py` / `diagnostics-extraction.json` | Diagnostic appendix extraction, exact support sets, absolute binned AUCs and 117,995 mechanical checks; parent reproduced the Markdown byte for byte |

The raw-score check deliberately covers the first, middle and last species in
the frozen primary panel's lexical order. It is not a numerical replay of all
157 species. The separate pre-opening audit covers every closed prediction,
and the aggregate checks cover all target-region score rows. No production
scorer or sklearn metric is imported by the raw-score checker.

`richness-check-initial.py` and `richness-check-initial-failure.json` preserve
the first verifier's inventory error. It expected region-panel rows only;
the frozen scorer correctly stores the full 157-by-three Cartesian inventory.
The 128 reported failures comprised 127 outside-panel row flags and one
inventory flag. The repaired verifier checks all 471 rows while leaving every
panel-specific summary rule intact. This correction changed no assessment
source or result.

The private canonical responses, prediction arrays, plan and complete returned
manifest remain under the original local run; full fitted states remain on
Deep. The final acceptance JSON one directory above binds these review files.

## Reproduce numerical checks

From the dSDM repository root, with the retained input artifacts present:

```sh
DSDM_OUTER_RUN=data/processed/dsdm/goal052-seawfb-dsdm-experiment/outer-assessment-20261003-r2
DSDM_OUTER_REVIEW=evidence/seawfb_dsdm/goal052/outer-review-20261005
python3 "$DSDM_OUTER_REVIEW/aggregate-check.py" "$DSDM_OUTER_RUN/scores.json"
python3 "$DSDM_OUTER_REVIEW/richness-check.py" \
  --scores "$DSDM_OUTER_RUN/scores.json" --plan "$DSDM_OUTER_RUN/plan.json" \
  --inner-summary evidence/seawfb_dsdm/goal052/summary.json \
  --output /tmp/dsdm-richness-recheck.json
uv run --frozen python "$DSDM_OUTER_REVIEW/independent-score-check.py" \
  --root "$PWD" --output /tmp/dsdm-independent-score-recheck.json
python3 "$DSDM_OUTER_REVIEW/diagnostics-extract.py" \
  --scores "$DSDM_OUTER_RUN/scores.json" --plan "$DSDM_OUTER_RUN/plan.json" \
  --inner-summary evidence/seawfb_dsdm/goal052/summary.json \
  --output /tmp/dsdm-diagnostics-recheck.md
```

Use new temporary output names for another check. Preserve the accepted review
files and the original failed and successful completion receipts.
