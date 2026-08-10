# Goal 038 - dSDM capacity diagnostic, Stage 1

Test whether a bounded architecture-capacity expansion changes the inner
multihead lift relative to the frozen Goal035 `resmlp13` control.  The scope
is `fraction100/full`, eight species, five held folds, and seeds 31031--31033.
The four prespecified variants are `wide512`, `deep6`, `deepwide6`, and
`deepwide6_drop10`; no alternative candidate or rescue is permitted.

Stage 1 does not open the outer vault. Labels, predictions, and leaves remain
private; only aggregate metrics, provenance, and gate arithmetic may be
tracked. Stage 2 is conditional within this already-approved Goal038 contract
and is added/executed automatically only if at most one Stage 1 variant passes
the frozen eligibility gate.

The Stage 2 contract is frozen now: if Stage 1 advances, exactly one variant
receives the six-method, seven-endpoint, five-seed Goal035-equivalent lifecycle
(40 cases, 8,840 logical artifacts, 17,640--17,680 physical fits). Confirmation
uses fresh seeds 31034--31035 on the five declared reduced-data endpoints; all
other paths are secondary diagnostics and nested endpoints/folds are not
independent confirmation units.
