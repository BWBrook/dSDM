# Goal 026 — Model-ready feature substrate

Freeze the deterministic pre-modelling feature substrate for the Goal024
`D_struct` map and Goal025 spatial partitions. Six split-fitted transforms
(`outer`, `cv_fold00`–`cv_fold04`) use continuous means and population SDs
from training map cells only. Categorical predictors remain nominal raw codes
with complete-map dictionaries and safe tokens. Features are materialised on
request as identity-bearing output with separate 25-column continuous and
3-column nominal categorical blocks; no model matrix is returned. Six
transformed map copies are not stored.

This gate makes no claim about model quality, performance, transfer,
occupancy, prevalence, or prediction.
