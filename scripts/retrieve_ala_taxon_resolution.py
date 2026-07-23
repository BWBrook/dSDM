#!/usr/bin/env python3
"""Retrieve the bounded Goal 010 official ALA evidence package."""

from pathlib import Path

from dsdm_phase1.ala_taxon_resolution import retrieve_ala_taxon_evidence


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "evidence" / "ala_taxon_resolution" / "2026-07-23"
BUNDLE = ROOT / "config" / "phase1_decision_bundle.json"


if __name__ == "__main__":
    print(retrieve_ala_taxon_evidence(output_dir=PACKAGE, bundle_path=BUNDLE))
