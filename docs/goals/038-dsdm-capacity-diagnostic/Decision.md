# Decision

The Goal035 `resmlp13` control is frozen at three constant residual blocks,
width 128, bottleneck 64, dropout 0, and weight decay 0.001 (60,865 trainable
parameters). New variants use constant/GELU/LayerNorm/AdamW, learning rate
0.001, batch size 128, maximum 300 epochs, patience 30, and weight decay
0.001. Exact parameter counts are 439,681 (`wide512`), 111,361 (`deep6`),
and 837,889 for each deep-wide variant.

For each species and held fold, common-seed predictions are averaged before
metrics. The primary per-species lift is multihead-full-finetune AUC minus
target-only AUC; interaction is variant lift minus control lift. TSS uses the
Goal036 pooled-OOF threshold; MCC is supplementary. Eligibility requires
median species interaction AUC > 0, median species absolute lift > 0,
interaction AUC > 0 in at least 5/8 species, positive species-balanced
interaction AUC for at least 2/3 seeds, and median interaction TSS >= 0.

This is a compute gate, not evidence of ecological superiority. Stage 2 is
implemented conditionally within Goal038 for the sole advanced candidate, with
no alternate-candidate rescue. The
frozen Stage 2 lifecycle covers all seven endpoints, five seeds, eight species,
five folds, and all six canonical methods: 40 atomic cases, 8,840 logical
artifacts, and 17,640--17,680 physical fits. Its fresh-seed confirmation subset
is seeds 31034--31035 over fraction25/ladder01, fraction25/ladder02, and the
three fraction50 ladders; it requires positive median interaction AUC in at
least 4/5 endpoints, positive five-endpoint species-average interaction AUC in
at least 5/8 species, positive aggregate interaction AUC for both fresh seeds,
and aggregate interaction TSS >= 0. Nested endpoints and folds are not
independent confirmation units.

The conditional Stage 2 runner is now implemented as a separate module and
config bound to the accepted Stage 1 aggregate/canary and the existing
Goal035--037 authorities. It fits only `wide512` when explicitly launched;
Stage 1 identities and receipts are immutable. No Stage 2 fit or outer access
was performed during implementation.

Stage 2 aggregate interaction TSS is defined as the mean across species of
each species' equally weighted mean across the five confirmation endpoints.
Descriptive six-method summaries cover all seven fitted endpoints; only the
five-endpoint target-only versus multihead contrast drives the gate. Thresholds,
endpoint/species contrasts, and aggregate TSS use only fresh seeds 31034--31035;
seeds 31031--31033 remain secondary descriptive evidence.
The tracked aggregate records all eight species' five-endpoint mean interaction
AUC values so the 5/8 gate and between-species heterogeneity are independently
auditable without disclosing row-level labels or predictions.

## Final Stage 2 decision

Stage 2 completed after pre-run commit `653aab8`: canary pass with deterministic
and finite predictions, 221 logical/441 physical fits, all substantive gates
true, and outer access 0/0; full run 40/40, invalid 0, 8,840 logical artifacts,
17,644 physical fits, approximately 36 minutes, outer access 0/0. The exact
validator exited 0.

Decision: `stop_no_confirmation`. Endpoint-positive was 1/5, species-positive
3/8, fresh-seed positive 0/2 (31034 = -0.0086863564; 31035 = -0.0114127387),
and aggregate D_TSS = -0.0132355477. Species mean D_AUC was: thylogale
-0.027426, notamacropus -0.033416, trichosurus -0.026415, pseudocheirus
-0.008569, vombatus -0.030896, sarcophilus +0.002904, dasyurus maculatus
+0.014089, and dasyurus viverrinus +0.015253. The Stage 1 width signal did not
replicate on fresh seeds/reduced endpoints; retain `resmlp13` for subsequent
work. The dasyurid-positive pattern is exploratory and not inferential. No
alternate rescue was opened and the outer seal remains intact.
