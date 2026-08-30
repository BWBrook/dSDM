# Decision

## Status

The Goal 046 executable correction is implemented and canary-ready. Production has not been run.

## Contract

Goal 046 is a paired correction of Goal 045, not a new model search. It uses the same three architectures, four arms, seeds, fold assignments, feature transforms, and full-target endpoint. The sole scientific change is strict removal of each focal target's contribution to auxiliary `X=3` support before pretraining or q fitting.

## Verification boundary

The focused suite and input gate must pass before any production launch. The two-epoch canary is an execution-path check only. Tasmania access is explicitly sealed at `0/0`; no transfer result is available from this Goal.
