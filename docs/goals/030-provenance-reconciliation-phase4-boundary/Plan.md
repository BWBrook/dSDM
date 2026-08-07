# Plan

## 1. Establish causes and safe boundaries

- Compare committed protocol hashes across Goal 029 acceptance.
- Trace Goal 028 and Goal 029 binding validation from config to failure.
- Compare Goal 025 tracked code/config/evidence history and frozen runtime
  receipts without reading ignored products.
- Inspect tests before selecting any executable gate.

## 2. Specify the repair with tests first

- Restore the immutable Goal 027 protocol bytes required by Goal 028's accepted
  receipt and both current configs.
- Preserve Goal 029's `src/dsdm_phase1/*.py` source binding.
- Characterize the boundary: sibling `src/dsdm/` changes are outside the seal;
  additions or edits within `src/dsdm_phase1/` change it.

## 3. Implement the minimum contract change

- Restore the protocol from its accepted pre-`4cab971` bytes.
- Place future Phase 4 implementation under sibling `src/dsdm/`.
- Mark only the two Goal 025 private full-replay tests as `real_scope`; require
  both their frozen CPython 3.14.4 runtime and the explicit
  `DSDM_RUN_GOAL025_PRIVATE_REPLAY=1` opt-in. Keep tracked-only gates active.
- Do not modify configs, production code, or evidence artifacts.

## 4. Validate proportionally

- Run the focused source-namespace characterization.
- Run safe Goal 028/029 contract and tamper tests selected after inspection.
- Run the Goal 029 plan command, `uv lock --check`, and `git diff --check`.
- Exclude the full suite without a fresh safety review; verify instead that the
  two private Goal 025 replays skip before their bodies without the opt-in.

## 5. Close out

- Update `Decision.md`, `Log.md`, and README with exact outcomes.
- Perform one focused diff review and one material repair pass if needed.
- Report residual risks and stop without commit or push.
