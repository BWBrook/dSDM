# Plan

1. Bind and validate the frozen Goal 045 design and mainland-only inputs.
2. Probe Alien without sending code or data; use the Mac CPU fallback if its
   Tailscale/SSH endpoint is unavailable.
3. Implement exact target exclusion, species-balanced pretraining, split-
   scoped stopping/replay, four matched target arms, private checkpoints, and
   aggregate validation.
4. Run a bounded two-epoch real-data canary without using its performance to
   revise the scientific design.
5. Commit and push the executable authority, then launch one resumable
   three-worker Mac CPU production run in detached `tmux`.
6. Stop after launch. On completion, validate every checkpoint and aggregate,
   review the scientific result once, and decide whether Goal 045 is accepted.
