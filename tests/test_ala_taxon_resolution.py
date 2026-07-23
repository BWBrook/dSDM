import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dsdm_phase1.ala_taxon_resolution import validate_evidence_package
from dsdm_phase1.contracts import ValidationError, load_phase1_decision_bundle


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "evidence" / "ala_taxon_resolution" / "2026-07-23"
BUNDLE = load_phase1_decision_bundle(ROOT / "config" / "phase1_decision_bundle.json")


class AlaTaxonResolutionTests(unittest.TestCase):
    def test_stored_package_has_nine_recommendable_candidates(self):
        result = validate_evidence_package(PACKAGE, bundle=BUNDLE)
        self.assertEqual(result, {"status": "validated", "species_count": 9, "recommendable_count": 9})
        candidates = json.loads((PACKAGE / "candidates.json").read_text())
        alias = next(c for c in candidates["candidates"] if c["species_id"] == "notamacropus_rufogriseus")
        self.assertEqual(alias["evidence_backed_aliases"], ["Macropus rufogriseus"])

    def test_fuzzy_match_mutation_fails_closed(self):
        with self._copy_package() as package:
            manifest = self._load(package / "manifest.json")
            record = manifest["records"][0]
            path = package / record["classification_file"]["path"]
            payload = self._load(path)
            payload["matchType"] = "fuzzyMatch"
            path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            record["classification_file"]["sha256"] = self._sha(path)
            (package / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            with self.assertRaises(ValidationError):
                validate_evidence_package(package, bundle=BUNDLE)

    def test_rank_or_classification_mutation_fails_closed(self):
        with self._copy_package() as package:
            manifest = self._load(package / "manifest.json")
            record = manifest["records"][1]
            path = package / record["classification_file"]["path"]
            payload = self._load(path)
            payload["rank"] = "genus"
            payload["classs"] = "Aves"
            path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            record["classification_file"]["sha256"] = self._sha(path)
            (package / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            with self.assertRaises(ValidationError):
                validate_evidence_package(package, bundle=BUNDLE)

    def test_duplicate_concept_id_fails_closed(self):
        with self._copy_package() as package:
            candidates_path = package / "candidates.json"
            candidates = self._load(candidates_path)
            candidates["candidates"][1]["taxon_concept_id"] = candidates["candidates"][0]["taxon_concept_id"]
            candidates_path.write_text(json.dumps(candidates, indent=2, sort_keys=True) + "\n")
            with self.assertRaises(ValidationError):
                validate_evidence_package(package, bundle=BUNDLE)

    def test_checksum_and_missing_response_fail_closed(self):
        with self._copy_package() as package:
            manifest = self._load(package / "manifest.json")
            path = package / manifest["records"][0]["simple_search_file"]["path"]
            path.unlink()
            with self.assertRaises(ValidationError):
                validate_evidence_package(package, bundle=BUNDLE)
        with self._copy_package() as package:
            manifest = self._load(package / "manifest.json")
            path = package / manifest["records"][0]["classification_file"]["path"]
            path.write_text(path.read_text() + "\n")
            with self.assertRaises(ValidationError):
                validate_evidence_package(package, bundle=BUNDLE)

    def test_invented_alias_fails_closed(self):
        with self._copy_package() as package:
            candidates_path = package / "candidates.json"
            candidates = self._load(candidates_path)
            candidate = next(c for c in candidates["candidates"] if c["species_id"] == "notamacropus_rufogriseus")
            candidate["evidence_backed_aliases"].append("Invented wallaby")
            candidates_path.write_text(json.dumps(candidates, indent=2, sort_keys=True) + "\n")
            with self.assertRaises(ValidationError):
                validate_evidence_package(package, bundle=BUNDLE)

    def test_forged_candidate_fields_and_concept_fail_closed(self):
        mutations = {
            "query": "Forged query",
            "returned_scientific_name": "Forged name",
            "authorship": "Forged author",
            "family": "Forgedidae",
            "synonym_type": "synonym",
            "taxon_concept_id": "https://biodiversity.org.au/afd/taxa/00000000-0000-0000-0000-000000000000",
        }
        for field, value in mutations.items():
            with self.subTest(field=field), self._copy_package() as package:
                candidates_path = package / "candidates.json"
                candidates = self._load(candidates_path)
                candidates["candidates"][0][field] = value
                candidates_path.write_text(json.dumps(candidates, indent=2, sort_keys=True) + "\n")
                with self.assertRaises(ValidationError):
                    validate_evidence_package(package, bundle=BUNDLE)

    def test_simple_search_species_id_and_roundtrip_disagreements_fail_closed(self):
        mutations = [
            ("simple_search_file", lambda payload: payload.update({"scientificName": "Forged name"})),
            ("classification_file", lambda payload: payload.update({"speciesID": "https://biodiversity.org.au/afd/taxa/00000000-0000-0000-0000-000000000000"})),
            ("taxon_roundtrip_file", lambda payload: payload.update({"taxonConceptID": "https://biodiversity.org.au/afd/taxa/00000000-0000-0000-0000-000000000000"})),
        ]
        for metadata_key, mutate in mutations:
            with self.subTest(metadata_key=metadata_key), self._copy_package() as package:
                self._mutate_response(package, 0, metadata_key, mutate)
                with self.assertRaises(ValidationError):
                    validate_evidence_package(package, bundle=BUNDLE)

    def test_bie_guid_and_accepted_detail_mutations_fail_closed(self):
        mutations = [
            ("bie_guid_file", lambda payload: payload[0].update({"acceptedIdentifier": "https://biodiversity.org.au/afd/taxa/00000000-0000-0000-0000-000000000000"})),
            ("bie_species_file", lambda payload: payload["taxonConcept"].update({"guid": "https://biodiversity.org.au/afd/taxa/00000000-0000-0000-0000-000000000000"})),
            ("bie_species_file", lambda payload: payload["taxonConcept"].update({"nameAuthority": "NOT_AFD"})),
            ("bie_species_file", lambda payload: payload["classification"].update({"family": "FORGEDIDAE"})),
            ("bie_species_file", lambda payload: payload.update({"identifiers": []})),
        ]
        for metadata_key, mutate in mutations:
            with self.subTest(metadata_key=metadata_key), self._copy_package() as package:
                self._mutate_response(package, 0, metadata_key, mutate)
                with self.assertRaises(ValidationError):
                    validate_evidence_package(package, bundle=BUNDLE)

    def test_manifest_status_url_query_openapi_and_unsafe_path_fail_closed(self):
        cases = ["status", "url", "method", "content_type", "query", "surfaces", "timestamp", "openapi", "unsafe_path"]
        for case in cases:
            with self.subTest(case=case), self._copy_package() as package:
                manifest_path = package / "manifest.json"
                manifest = self._load(manifest_path)
                if case == "status":
                    manifest["records"][0]["classification_file"]["status"] = 201
                elif case == "url":
                    manifest["records"][0]["simple_search_file"]["url"] = "https://evil.example/search"
                elif case == "method":
                    manifest["records"][0]["simple_search_file"]["method"] = "POST"
                elif case == "content_type":
                    manifest["records"][0]["simple_search_file"]["content_type"] = "text/plain"
                elif case == "query":
                    manifest["records"][0]["query"] = "Forged query"
                elif case == "surfaces":
                    manifest["official_surfaces"]["bie"] = "https://evil.example/bie"
                elif case == "timestamp":
                    manifest["retrieved_at"] = "2026-07-23T10:07:15+00:00"
                elif case == "unsafe_path":
                    manifest["records"][0]["classification_file"]["path"] = "../outside.json"
                elif case == "openapi":
                    openapi_path = package / manifest["openapi"]["path"]
                    openapi_path.write_text("{}\n")
                    manifest["openapi"]["sha256"] = self._sha(openapi_path)
                manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
                with self.assertRaises(ValidationError):
                    validate_evidence_package(package, bundle=BUNDLE)

    def test_alias_relabelling_fails_closed(self):
        with self._copy_package() as package:
            manifest = self._load(package / "manifest.json")
            alias = manifest["records"][1]["alias_evidence"][0]
            alias["alias"] = "Wallabia rufogrisea"
            (package / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            with self.assertRaises(ValidationError):
                validate_evidence_package(package, bundle=BUNDLE)

    def _copy_package(self):
        temp = tempfile.TemporaryDirectory()
        destination = Path(temp.name) / "package"
        shutil.copytree(PACKAGE, destination)
        class Context:
            def __enter__(self_nonlocal):
                return destination
            def __exit__(self_nonlocal, exc_type, exc, tb):
                temp.cleanup()
        return Context()

    def _mutate_response(self, package, record_index, metadata_key, mutate):
        manifest_path = package / "manifest.json"
        manifest = self._load(manifest_path)
        metadata = manifest["records"][record_index][metadata_key]
        path = package / metadata["path"]
        payload = self._load(path)
        mutate(payload)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        metadata["sha256"] = self._sha(path)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    @staticmethod
    def _load(path):
        return json.loads(path.read_text())

    @staticmethod
    def _sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
