# Goal052 post hoc bird extent and ensemble review

This dated supplement reproduces aggregate-only extent and ensemble checks from the accepted Goal052 saved predictions. It does not refit or tune models. Inner OOF scores retain the published mean-fold values and add pooled whole-domain, named-region pooled, and named-region-by-fold summaries. Eligible strata are averaged within target and targets are then equally weighted.

The response-free ledger contains 787,357 retained cells: 360,625 have NULL region because they are the domain complement and are included only in whole-domain summaries. The outer domain contains 144,860 cells, all bound to NCP (Naracoorte Coastal Plain), SEH (South Eastern Highlands), and NNC (NSW North Coast); no NULL region occurs in the outer domain. Across the primary 73, the named-region pooled calculation used 696 eligible target×region strata and the named-region×fold calculation used 2,650 eligible target×region×fold strata; each target was then weighted equally. Outer summaries use the accepted X10 mask: all presences plus focal-excluded richness at least 10.

## Primary 73 comparison means

| Aggregation | FT AUC | TO AUC | FT−TO | FT−conv | FT+conv−conv | TO+conv−conv |
|---|---:|---:|---:|---:|---:|---:|
| Published mean-fold | 0.831603 | 0.825822 | 0.005781 | 0.003390 | 0.005804 | 0.003090 |
| Pooled whole-domain | 0.832677 | 0.826557 | 0.006121 | 0.003111 | 0.005779 | 0.002922 |
| Named-region pooled | 0.691116 | 0.680158 | 0.010958 | 0.003702 | 0.009374 | 0.004288 |
| Named-region×fold | 0.689709 | 0.682465 | 0.007244 | 0.005916 | 0.009970 | 0.006216 |
| Outer equal-region then species | 0.682732 | 0.683128 | -0.000396 | 0.002771 | 0.010352 | 0.009621 |

The accepted X10 replay gate compared 2,870 saved-score AUCs across all verified 157-target region records and every saved arm; the largest observed absolute error was 0 (tolerance 1e-12). The exploratory target-only/conventional ensemble uses unchanged saved predictions. The SEH tail is retained for all 73 primary species, with undefined scores kept as NA rather than excluded silently. These extent summaries do not identify a geographic penalty, and ensemble similarity does not establish that pretraining contributes no information.
