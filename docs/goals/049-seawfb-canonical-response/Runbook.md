# Goal 049 runbook

## Preconditions

- Work from the clean action-repo `main` branch.
- Do not read or use occurrence support while constructing Stage A roles.
- Keep all authority payloads, taxonomy payloads, species-cell lists, and
  canonical matrices below the ignored private Goal 049 root.
- Tracked outputs contain only hashes, counts, names/roles, decisions, and
  privacy-safe summaries.

## Ordered execution

The implementation must expose separate commands for:

1. authority retrieval and count-free registry construction;
2. ALA taxonomy freeze;
3. Stage A validation and tracked freeze receipt;
4. Goal 048 receipt promotion audit plus new-species canary;
5. resumable aggregate census;
6. canonical substrate and panel construction; and
7. final validation.

The Stage B commands must refuse to run unless the complete Stage A freeze
receipt matches the current config and private inputs.

## Long-run cadence

If the aggregate census is projected to exceed an interactive work period,
run it in a named local `tmux` session because it is network-bound,
checkpointed, and requires access to the local ignored substrate. Record the
exact launch command, session name, log path, progress path, and completion
marker. Do not busy-wait. Barry can wake the orchestrator after the run stops.

## Failure policy

Stop immediately on unresolved taxonomy, shared identifiers, authority drift,
total/facet mismatch, truncation, missing coordinates, checkpoint identity
drift, transport-limit breach, private-data leakage, or fewer than 20 common
targets. Do not weaken the scientific contract to force completion.
