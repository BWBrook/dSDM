# Goal 033 - neutral real-data architecture selection

Select one shared residual-MLP architecture for the real eight-species dSDM
workflow. The selector is target-only, uses `fraction100/full`, and is based
only on outer-training inner cross-validation. Goal032's 77-feature substrate
and sealed outer boundary remain authoritative.

The fixed workload is 960 screen logical evaluations (24 architectures × 8
species × 5 held folds × one seed), followed by 480 fresh shortlist logical
evaluations (top four × 8 × 5 × three seeds). Discovery plus exact replay
means 2,880 physical fits. The final winner is ranked on shortlist metrics
only; screen metrics are not blended into the final score.

No outer assessment is attempted or opened. Inner held labels and predictions
remain private; tracked evidence contains aggregates, rankings, digests, and
runtime attestation only.

The config freezes all scope, execution, privacy, runtime, and evidence fields
and binds the six execution-critical source modules by SHA256. Bundle and leaf
identities include the Goal033 config digest and actual runtime-attestation
digest. `run` is private-only; aggregate publication occurs only through
`finalize` after orchestrator review and wake-up.
