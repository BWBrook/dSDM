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

This is a compute gate, not evidence of ecological superiority. Stage 2 is not
implemented in this tranche; if the gate advances a candidate, it is added and
executed conditionally within Goal038, with no alternate-candidate rescue. The
frozen Stage 2 lifecycle covers all seven endpoints, five seeds, eight species,
five folds, and all six canonical methods: 40 atomic cases, 8,840 logical
artifacts, and 17,640--17,680 physical fits. Its fresh-seed confirmation subset
is seeds 31034--31035 over fraction25/ladder01, fraction25/ladder02, and the
three fraction50 ladders; it requires positive median interaction AUC in at
least 4/5 endpoints, positive five-endpoint species-average interaction AUC in
at least 5/8 species, positive aggregate interaction AUC for both fresh seeds,
and aggregate interaction TSS >= 0. Nested endpoints and folds are not
independent confirmation units.
