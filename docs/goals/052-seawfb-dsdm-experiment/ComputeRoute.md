# Goal052 compute decision — 12 September 2026

Status: the approved 24-hour pilot stopped at its cap on 13 September,
with two verified pretraining checkpoints and no target or ecological results.
The eight-worker qualification passed on 13 September. Its approved 48-hour
continuation launched at 17:10 AEST with four-hour checks. Barry granted
standing compute allocation authority; review and select further resources
autonomously. `PilotReview.md` and `pilot8-launch.json` record the active run.
The original approved plan and qualification measurements follow.

## Verified measurement

Source `e309ca8` (identity
`fce7fb52b386c662c198e264aebc007de203e363b5ccc917ccd55ebaa2470926`)
passed the two-worker deterministic canary and the uncapped one-epoch profile.
The profile exited zero; its returned SHA-256 is
`b580e1fd551deb1f51d6b4a3f87f1ac020c96a05d78aad4884fa6d70e20a102f`.
The independent review is `evidence/seawfb_dsdm/goal052/full-profile-review.json`.

| Measurement | Observed value |
| --- | ---: |
| Full auxiliary heads / unique feature cells | 168 / 98,708 |
| Auxiliary discovery / stopping / replay rows | 6,895,417 / 2,737,414 / 9,632,831 |
| One discovery epoch, stopping pass and replay epoch | 79.54 minutes |
| Target-only / target plus q / full fine-tuning lifecycle | 12.64 / 12.68 / 12.77 seconds |
| Frozen-trunk target lifecycle | 4.55 seconds |
| Target discovery / stopping / replay rows | 42,024 / 16,658 / 58,682 |
| Entire profile, including assembly and four target arms | 80.57 minutes |
| Peak worker RSS | 2.395 GiB |

All fits used CPU foreach AdamW. Source, accepted baseline, host, q hash,
row counts, seed namespaces, finite losses/state, reset/replay, transfer and
frozen-trunk invariants passed inspection. The profile caps the epoch count
at one solely for measurement; it does not estimate a selected production
epoch or provide ecological performance. Held prediction was limited to
1,024 rows per arm. The frozen production settings remain maximum 300 epochs,
patience 30, minimum improvement 1e-5 and batch size 128.

Server load varied substantially during the profile: approximately 57 at the
start, 17 at the intermediate check, and 48 at the 16:18 AEST completion check.
At the latter check there were 48 processes above 50% CPU and 118 GiB available
RAM. The host has 32 physical cores / 64 logical CPUs. Timing under this
changing co-run load is not an idle-machine forecast. Two workers are the
qualified concurrency; larger concurrency requires a new capacity check and
appropriate qualification.

## Why a bounded pilot

The full inventory has 900 pretraining and 42,345 unique target lifecycles.
The historical `workload.json` remains valid row accounting, with its original
source identity retained; the optimizer change did not alter that inventory.
Actual selected epochs are unmeasured. Every successful full-budget lifecycle
needs at least 31 discovery/stopping epochs and one replay epoch. Row counts
alone cannot supply a wall-time lower bound because training, stopping,
architecture, head count and frozen-trunk costs differ. The largest-architecture
profile must not be multiplied uniformly across the experiment and presented
as a precise forecast.

The pilot uses the existing frozen scheduler and checkpoint contracts. It
starts with the canonical architecture-screen pretraining tasks (block 0,
fold 0, bridge_control and bridge_wide are first), then advances in the
existing order within its resource cap. Completed, verified checkpoints are
reusable. A fit interrupted at the deadline has no resumable within-fit state;
its incomplete work must be repeated. A 24-hour cap may therefore return few
or no completed lifecycles and is not a promise to complete the screen.

Review completed epoch histories, replay counts, checkpoint invariants and
actual throughput before any larger commitment. No partial-grid ecological
scores or performance-driven protocol changes are permitted. A later GPU route
would need its own locked-environment and full-row qualification; neither a
GPU speedup nor CUDA compatibility has been established for this workflow.
The current Alien driver route is unresolved; Nectar allocation and driver
changes are not part of this pilot. Nectar remains parked.

## Approved launch and deadline

The wrapper `scripts/goal052_pilot.sh` has passed shell syntax validation.
GNU timeout 9.4 is present on deep-server. A temporary process-tree probe
confirmed that its deadline returns 124 and terminates the child process group.
It allows at most two training workers for 24 hours, sends TERM at the deadline,
and permits 60 seconds before KILL. It writes a separate pilot exit marker;
124 is the expected time-cap outcome, while 137 may indicate forced shutdown.
Neither is a successful experiment-completion marker.

The wrapper was staged without changing the bound scientific source. Source
and both qualification identities were checked before launch; server load
was 48.11 and available RAM 118 GiB. Launch command:

```sh
tmux new-session -d -s dsdm-goal052-pilot \
  'bash /data/codex/repos/dSDM/scripts/goal052_pilot.sh /data/codex/repos/dSDM'
```

At the deadline, verify no pilot worker remains, retain completed leaves and
logs, and return the measured cost and a next-route recommendation. Do not
continue beyond the cap without the ensuing resource decision. The existing
follow-up now checks the pilot every four hours. Its cadence is independent
of the wrapper's enforced deadline. See the bound `pilot-launch.json` receipt
in the private run root and `evidence/seawfb_dsdm/goal052/`.
