# Runbook

Run production with:

```sh
PYTHONPATH=src uv run --locked python -m dsdm_phase1.pseudoabsence_derivation --root .
```

Validate tracked evidence without private output access:

```sh
PYTHONPATH=src uv run --locked python -c 'from pathlib import Path; from dsdm_phase1.pseudoabsence_derivation import validate_evidence; print(validate_evidence(Path("config/pseudoabsence_derivation_plan.json"), Path("evidence/pseudoabsence_derivation/2026-07-26")))'
```

Validate full private replay and semantic evidence:

```sh
PYTHONPATH=src uv run --locked python -c 'from pathlib import Path; from dsdm_phase1.pseudoabsence_derivation import validate_evidence; print(validate_evidence(Path("config/pseudoabsence_derivation_plan.json"), Path("evidence/pseudoabsence_derivation/2026-07-26"), full=True))'
```
The run fails closed when bound inputs or destinations drift; generated output
and evidence directories must be absent before publication.
