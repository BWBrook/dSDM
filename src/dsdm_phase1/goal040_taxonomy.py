"""AMTC-led, region-safe taxon and query-path freeze for Goal 040."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from urllib.request import Request, urlopen


AMTC_VERSION = "5.0 (February 2026)"
AMTC_SHA256 = "c2d0ffe8e12901655017a238fd8593cea3bd9c5641871906d961b5ab16b513a6"
ANCHORS = {
    "Notamacropus rufogriseus", "Trichosurus vulpecula",
    "Pseudocheirus peregrinus", "Vombatus ursinus", "Dasyurus maculatus",
}
ADDITIONAL_MAINLAND_DONORS = {
    "Phascolarctos cinereus", "Petauroides volans", "Petaurus australis",
    "Petaurus norfolcensis", "Petrogale penicillata", "Phascogale tapoatafa",
    "Sminthopsis crassicaudata", "Potorous longipes", "Sminthopsis leucopus",
    "Gymnobelideus leadbeateri", "Pseudomys novaehollandiae", "Mastacomys fuscus",
    "Pseudomys fumeus", "Burramys parvus",
    "Pseudomys shortridgei",
}
DONOR_IBRA_TOKEN = {
    "Phascolarctos cinereus": "Australian Alps",
    "Petauroides volans": "South Eastern Highlands",
    "Petaurus australis": "South Eastern Highlands",
    "Petaurus norfolcensis": "Victorian Midlands",
    "Petrogale penicillata": "South East Corner",
    "Phascogale tapoatafa": "Australian Alps",
    "Sminthopsis crassicaudata": "Australian Alps",
    "Potorous longipes": "South East Corner",
    "Sminthopsis leucopus": "Australian Alps",
    "Gymnobelideus leadbeateri": "South Eastern Highlands",
    "Pseudomys novaehollandiae": "South East Coastal Plain",
    "Mastacomys fuscus": "Australian Alps",
    "Pseudomys fumeus": "South Eastern Highlands",
    "Burramys parvus": "Australian Alps",
    "Pseudomys shortridgei": "Victorian Midlands",
}
QUERY_TAXA = ANCHORS | {"Macropus giganteus"} | ADDITIONAL_MAINLAND_DONORS
MARINE_FAMILIES = {
    "Balaenidae", "Balaenopteridae", "Delphinidae", "Kogiidae",
    "Neobalaenidae", "Physeteridae", "Ziphiidae", "Otariidae", "Phocidae",
    "Dugongidae",
}
STRONGLY_AQUATIC = {
    "Ornithorhynchus anatinus", "Hydromys chrysogaster", "Xeromys myoides",
}
LEDGER_FIELDS = [
    "scientific_name", "common_name", "amtc_order", "amtc_family",
    "global_extant_status", "global_extant_basis",
    "current_native_extant_mainland_status", "mainland_status_basis",
    "current_native_extant_tasmania_status", "tasmania_status_basis",
    "primary_cohort_decision", "decision_reason", "review_status",
    "ala_discovery_crosscheck", "ala_accepted_name", "ala_accepted_concept_id",
    "query_roles", "shared_evaluation_eligible", "shared_override_basis",
    "query_strategy", "query_concepts", "accepted_descendants",
    "evidence_backed_aliases", "provider_record_deduplication",
    "regional_evidence_ids",
]


ROLE_STATUS = {
    "Notamacropus rufogriseus": ("yes", "yes", "anchor_shared", ["tas_macropods", "coolah"]),
    "Trichosurus vulpecula": ("yes", "yes", "anchor_shared", ["brushtail"]),
    "Pseudocheirus peregrinus": ("yes", "yes", "anchor_shared", ["ringtail"]),
    "Vombatus ursinus": ("yes", "yes", "anchor_shared", ["wombat"]),
    "Dasyurus maculatus": ("yes", "yes", "anchor_shared", ["spotted_quoll"]),
    "Macropus giganteus": ("yes", "yes", "mainland_only_by_decision", ["forester"]),
    "Dasyurus viverrinus": ("no_extant_native_wild_population", "yes", "nonquery_regional_only", ["eastern_quoll"]),
    "Thylogale billardierii": ("no_extant_native_population", "yes", "nonquery_regional_only", ["pademelon"]),
    "Sarcophilus harrisii": ("no_extant_native_population", "yes", "nonquery_regional_only", ["tas_mammals"]),
    "Petaurus breviceps": ("yes", "introduced_or_taxonomically_misattributed", "nonquery_introduced_ambiguity", ["glider_introduction"]),
    "Petaurus notatus": ("yes", "introduced", "nonquery_introduced_ambiguity", ["glider_introduction"]),
}


SOURCES = {
    "tas_macropods": {
        "url": "https://parks.tas.gov.au/discovery-and-learning/wildlife/land-mammals/kangaroos-and-wallabies",
        "tokens": ["Notamacropus rufogriseus", "Macropus giganteus", "Tasmania has five species"],
        "claim": "Tasmania Parks lists Bennett's wallaby and Forester kangaroo among Tasmania's five macropods.",
    },
    "coolah": {
        "url": "https://australian.museum/learn/news/blog/islands-in-the-sky-sampling-the-fauna-of-coolah-tops/",
        "tokens": ["Notamacropus rufogriseus", "Macropus giganteus", "Coolah Tops"],
        "claim": "Australian Museum reports both species currently observed at Coolah Tops in the selected mainland domain.",
    },
    "brushtail": {
        "url": "https://australian.museum/learn/animals/mammals/common-brushtail-possum/",
        "tokens": ["Trichosurus vulpecula", "New South Wales", "Tasmania"],
        "claim": "Australian Museum gives current mainland-state and Tasmania distribution.",
    },
    "ringtail": {
        "url": "https://australian.museum/learn/animals/mammals/common-ringtail-possum/",
        "tokens": ["Pseudocheirus peregrinus", "New South Wales", "Tasmania"],
        "claim": "Australian Museum gives current mainland-state and Tasmania distribution.",
    },
    "wombat": {
        "url": "https://australian.museum/learn/animals/mammals/bare-nosed-wombat/",
        "tokens": ["Vombatus ursinus", "southeastern Australia", "Tasmania"],
        "claim": "Australian Museum describes the fragmented current southeastern-mainland and Tasmanian distribution.",
    },
    "spotted_quoll": {
        "url": "https://www.dcceew.gov.au/environment/biodiversity/threatened/assessments/dasyurus-maculatus",
        "tokens": ["Dasyurus maculatus", "southeastern mainland", "Tasmanian population"],
        "claim": "DCCEEW separately identifies current southeastern-mainland and Tasmanian populations.",
    },
    "forester": {
        "url": "https://nre.tas.gov.au/wildlife-site/Pages/Forester-Kangaroo.aspx",
        "tokens": ["Macropus giganteus", "common on mainland Australia", "currently restricted"],
        "claim": "NRE Tasmania states current mainland and restricted Tasmanian populations.",
    },
    "eastern_quoll": {
        "url": "https://www.dcceew.gov.au/environment/biodiversity/threatened/species/20-mammals-by-2020/eastern-quoll",
        "tokens": ["Dasyurus viverrinus", "disappeared from the Australian mainland", "remain only in Tasmania"],
        "claim": "DCCEEW distinguishes the remaining native wild Tasmanian population from mainland reintroductions.",
    },
    "pademelon": {
        "url": "https://nre.tas.gov.au/Documents/Effects%20of%20Hunting%20and%20Rainfall%20on%20Bennetts%20Wallaby%20and%20Tasmanian%20Pademelon%20Populations.pdf",
        "tokens": ["Thylogale billardierii", "now restricted to Tasmania"],
        "claim": "NRE Tasmania reports the pademelon as extant in Tasmania and no longer extant on the mainland.",
    },
    "tas_mammals": {
        "url": "https://nre.tas.gov.au/wildlife-management/fauna-of-tasmania/mammals/complete-listing-of-tasmanias-mammals",
        "tokens": ["Sarcophilus harrisii", "Tasmanian devil"],
        "claim": "NRE Tasmania lists the Tasmanian devil as a current Tasmanian mammal; AMTC extant status and known mainland loss preclude shared use.",
    },
    "glider_introduction": {
        "url": "https://researchprofiles.canberra.edu.au/en/publications/when-is-a-native-species-invasive-incursion-of-a-novel-predatory-",
        "tokens": ["Petaurus breviceps", "recent introduction", "Tasmania"],
        "claim": "Peer-reviewed research metadata supports a recent Tasmanian introduction under the pre-split name.",
    },
}


DESCENDANTS = {
    "Phascogale tapoatafa": [
        ("Phascogale tapoatafa tapoatafa", "https://biodiversity.org.au/afd/taxa/917d6c91-db7c-4869-9d37-40265919b8b1"),
    ],
    "Sminthopsis crassicaudata": [
        ("Sminthopsis crassicaudata crassicaudata", "https://biodiversity.org.au/afd/taxa/9c06f8c7-340f-4364-9a69-3189b949f8ee"),
    ],
    "Notamacropus rufogriseus": [
        ("Notamacropus rufogriseus banksianus", "https://biodiversity.org.au/afd/taxa/8c42d177-17cb-4dcf-bff6-d30d47bfa9d2"),
        ("Notamacropus rufogriseus rufogriseus", "https://biodiversity.org.au/afd/taxa/a8d6dc61-960b-4275-8427-a85de20f585a"),
    ],
    "Trichosurus vulpecula": [
        ("Trichosurus vulpecula fuliginosus", "https://biodiversity.org.au/afd/taxa/15e7278f-5f69-4f1e-b9f8-022ca8fcd417"),
        ("Trichosurus vulpecula vulpecula", "https://biodiversity.org.au/afd/taxa/ef644032-3c35-41e9-95ae-bd2c506fdc07"),
    ],
    "Pseudocheirus peregrinus": [
        ("Pseudocheirus peregrinus convolutor", "https://biodiversity.org.au/afd/taxa/5b2015b0-8883-481b-96dc-147009c042f6"),
        ("Pseudocheirus peregrinus cooki", "https://biodiversity.org.au/afd/taxa/15ff1860-30c5-4fde-a066-6f9d5dd67d60"),
        ("Pseudocheirus peregrinus peregrinus", "https://biodiversity.org.au/afd/taxa/f3e43080-9e6a-4ad3-ab35-f3ecd70b5976"),
        ("Pseudocheirus peregrinus pulcher", "https://biodiversity.org.au/afd/taxa/ffc67963-930a-4666-a094-6066ceb434f7"),
    ],
    "Vombatus ursinus": [
        ("Vombatus ursinus hirsutus", "https://biodiversity.org.au/afd/taxa/e4b74750-7541-4c67-89d1-5b5718b30ea7"),
        ("Vombatus ursinus tasmaniensis", "https://biodiversity.org.au/afd/taxa/3e53b354-2b48-4a2a-af29-acd8ecdfe1e6"),
        ("Vombatus ursinus ursinus", "https://biodiversity.org.au/afd/taxa/76b2b77b-6092-47dd-8de1-00e504b1e383"),
    ],
    "Dasyurus maculatus": [
        ("Dasyurus maculatus maculatus", "https://biodiversity.org.au/afd/taxa/c4d41c94-ad01-4fc1-a797-032ff6a10233"),
    ],
    "Macropus giganteus": [],
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _regional_basis(status: str, evidence_ids: list[str], region: str) -> str:
    if status == "not_assessed_nonquery":
        return f"not assessed because no {region} query/support role"
    if status == "no_global_extinction":
        return f"AMTC {AMTC_VERSION} global-extinction classification"
    if not evidence_ids:
        raise ValueError(f"assessed {region} status lacks regional evidence")
    return _json(evidence_ids)


def _fetch_sources(root: Path) -> dict:
    raw = root / "data/raw/goal040/references/regional_roles"
    raw.mkdir(parents=True, exist_ok=True)
    output = {}
    for source_id, spec in SOURCES.items():
        suffix = ".pdf" if spec["url"].lower().endswith(".pdf") else ".html"
        path = raw / f"{source_id}{suffix}"
        if not path.exists():
            request = Request(spec["url"], headers={"User-Agent": "dSDM-Goal040/2.0"})
            with urlopen(request, timeout=180) as response:
                path.write_bytes(response.read())
        if suffix == ".pdf":
            import subprocess
            parsed = subprocess.run(
                ["pdftotext", str(path), "-"], check=True, capture_output=True, text=True
            ).stdout
        else:
            parsed = re.sub(r"<[^>]+>", " ", path.read_text(encoding="utf-8", errors="ignore"))
        normal = " ".join(parsed.split()).lower()
        missing = [token for token in spec["tokens"] if token.lower() not in normal]
        if missing:
            raise ValueError(f"regional source {source_id} lacks required parsed evidence: {missing}")
        output[source_id] = {
            "url": spec["url"], "sha256": _sha(path), "claim": spec["claim"],
            "parsed_tokens": spec["tokens"],
        }
    return output


def _amtc_frame(root: Path) -> list[dict[str, object]]:
    xlsx = root / "data/raw/goal040/references/amtc_australian_mammal_species_list_version_5_0.xlsx"
    parsed = root / "data/raw/goal040/references/amtc_csv/amtc_australian_mammal_species_list_version_5_0.csv"
    if not xlsx.exists() or _sha(xlsx) != AMTC_SHA256 or not parsed.exists():
        raise ValueError("AMTC v5.0 source or parsed derivative is absent/checksum-drifted")
    rows = []
    with parsed.open(encoding="utf-8-sig", newline="") as handle:
        next(handle)
        order = family = ""
        for raw in csv.DictReader(handle):
            heading = (raw.get("Higher taxonomic rank summary") or "").strip()
            if heading.startswith("Order "):
                order = heading.removeprefix("Order ").strip()
            if heading.startswith("Family "):
                family = heading.removeprefix("Family ").strip()
            genus = (raw.get("Genus") or "").strip()
            species_raw = (raw.get("species") or "").strip()
            subspecies = (raw.get("subspecies") or "").strip()
            if genus and species_raw and not subspecies:
                rows.append({
                    "scientific_name": " ".join((genus, species_raw.replace("†", "").strip())),
                    "common_name": (raw.get("Common Name") or "").strip(),
                    "order": order, "family": family, "extinct": "†" in species_raw,
                })
    if len(rows) != 416 or len({row["scientific_name"] for row in rows}) != 416:
        raise ValueError("AMTC species-level frame drift")
    return rows


def _discovery(root: Path) -> dict[str, dict[str, str]]:
    path = root / "data/raw/goal040/taxonomy/atlas_species_mammalia_2001_2025_bbox.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["Species Name"]: row for row in csv.DictReader(handle)}


def _validated_query(root: Path, name: str, discovery: dict[str, dict[str, str]]) -> tuple[str, list[dict]]:
    row = discovery.get(name)
    if row is None:
        raise ValueError(f"query taxon {name} absent from ALA cross-check")
    concept = row["Species"]
    raw_key = hashlib.sha256(concept.encode()).hexdigest()[:20]
    concept_dir = root / "data/raw/goal040/taxonomy/concepts"
    bie = json.loads((concept_dir / f"{raw_key}.bie.json").read_text(encoding="utf-8"))
    taxon = bie.get("taxonConcept", {})
    if (
        taxon.get("guid") != concept or taxon.get("nameString") != name
        or taxon.get("rankString") != "species" or taxon.get("taxonomicStatus") != "accepted"
    ):
        raise ValueError(f"accepted-concept BIE GUID round-trip failed for {name}")
    children = json.loads((concept_dir / f"{raw_key}.children.json").read_text(encoding="utf-8"))
    actual = {(child.get("name"), child.get("guid"), child.get("rank")) for child in children}
    reviewed = DESCENDANTS.get(name)
    if reviewed is None:
        reviewed = sorted(
            (child.get("name"), child.get("guid"))
            for child in children
            if child.get("rank") == "subspecies"
            and str(child.get("name", "")).startswith(name + " ")
            and str(child.get("guid", "")).startswith("https://biodiversity.org.au/afd/taxa/")
        )
    if any((child_name, child_id, "subspecies") not in actual for child_name, child_id in reviewed):
        raise ValueError(f"reviewed descendant evidence drift for {name}")
    return concept, [{"name": child_name, "concept_id": child_id, "rank": "subspecies"} for child_name, child_id in reviewed]


def build_taxon_freeze(root: Path) -> tuple[list[dict[str, str]], dict]:
    frame = _amtc_frame(root)
    discovery = _discovery(root)
    sources = _fetch_sources(root)
    bie_donor_evidence = {}
    output = []
    for taxon in frame:
        name = str(taxon["scientific_name"])
        extinct = bool(taxon["extinct"])
        discovery_row = discovery.get(name, {})
        mainland = tasmania = "not_assessed_nonquery"
        evidence_ids: list[str] = []
        role_class = ""
        if name in ROLE_STATUS:
            mainland, tasmania, role_class, evidence_ids = ROLE_STATUS[name]
        elif name in ADDITIONAL_MAINLAND_DONORS:
            mainland, tasmania = "yes", "not_assessed_nonquery"
            role_class = "mainland_only_by_current_jurisdiction_evidence"
            evidence_ids = [f"bie_current_vic_act:{name}"]
        if extinct:
            decision, reason, review = "exclude", "globally_extinct_AMTC_dagger", "resolved_excluded"
            mainland = tasmania = "no_global_extinction"
        elif taxon["order"] == "Chiroptera":
            decision, reason, review = "exclude", "bat_excluded", "resolved_excluded"
        elif taxon["family"] in MARINE_FAMILIES or taxon["order"] == "Sirenia":
            decision, reason, review = "exclude", "marine_mammal_excluded", "resolved_excluded"
        elif name in STRONGLY_AQUATIC:
            decision, reason, review = "exclude", "strongly_aquatic_specialist_excluded", "resolved_excluded"
        elif name in QUERY_TAXA:
            decision, reason, review = "include", "current_native_extant_regional_evidence", "resolved_query_role"
        else:
            decision, reason, review = "nonquery", "no_decision_grade_exact-domain_regional_evidence", "nonquery_pending_regional_evidence"

        roles: list[str] = []
        shared = False
        override = ""
        query_strategy = "not_query_eligible"
        query_concepts: list[str] = []
        descendants: list[dict] = []
        if name in QUERY_TAXA:
            concept, descendants = _validated_query(root, name, discovery)
            if name in ADDITIONAL_MAINLAND_DONORS:
                raw_key = hashlib.sha256(concept.encode()).hexdigest()[:20]
                bie_path = root / "data/raw/goal040/taxonomy/concepts" / f"{raw_key}.bie.json"
                afd_path = root / "data/raw/goal040/taxonomy/concepts" / f"{raw_key}.afd.html"
                bie = json.loads(bie_path.read_text(encoding="utf-8"))
                statuses = {
                    jurisdiction: detail.get("status")
                    for jurisdiction, detail in bie.get("conservationStatuses", {}).items()
                    if jurisdiction in {"VIC", "ACT"}
                    and "Extinct" not in str(detail.get("status", ""))
                }
                if not statuses:
                    raise ValueError(f"mainland donor lacks current VIC/ACT status evidence: {name}")
                ibra_token = DONOR_IBRA_TOKEN[name]
                if not afd_path.exists() or ibra_token.lower() not in afd_path.read_text(
                    encoding="utf-8", errors="ignore"
                ).lower():
                    raise ValueError(f"mainland donor lacks selected-IBRA corroboration: {name}")
                bie_donor_evidence[name] = {
                    "accepted_concept_id": concept, "bie_response_sha256": _sha(bie_path),
                    "afd_response_sha256": _sha(afd_path),
                    "current_jurisdiction_statuses": statuses,
                    "selected_ibra_region_token_parsed_from_afd": ibra_token,
                    "basis": "AMTC native/extant frame plus current ALA BIE-aggregated VIC/ACT legal status, with AFD IBRA text used only to corroborate intersection with the selected domain (not contemporary status)",
                }
            query_concepts = [concept] + [item["concept_id"] for item in descendants]
            query_strategy = "explicit_reviewed_parent_plus_domain_relevant_accepted_descendants_union"
            roles = ["mainland_donor_pretraining"]
            if name in ANCHORS:
                roles += ["tasmania_support", "shared_evaluation_candidate"]
                shared = True
            elif name == "Macropus giganteus":
                override = "Barry-approved Macropus giganteus shared-evaluation exclusion; mainland donor role only"

        aliases = []
        if name == "Macropus giganteus":
            aliases = [{
                "name": "Macropus giganteus tasmaniensis",
                "query": 'taxa:"Macropus giganteus tasmaniensis"',
                "basis": "Goal012 normalized-name containment 398/398; concept-ID alias returned zero",
                "regional_use": "not a Tasmania support role; retained only as an evidence-backed normalization path",
            }]

        output.append({
            "scientific_name": name, "common_name": str(taxon["common_name"]),
            "amtc_order": str(taxon["order"]), "amtc_family": str(taxon["family"]),
            "global_extant_status": "no" if extinct else "yes",
            "global_extant_basis": f"AMTC Australian Mammal Species List {AMTC_VERSION}; dagger={'yes' if extinct else 'no'}",
            "current_native_extant_mainland_status": mainland,
            "mainland_status_basis": _regional_basis(mainland, evidence_ids, "mainland"),
            "current_native_extant_tasmania_status": tasmania,
            "tasmania_status_basis": _regional_basis(tasmania, evidence_ids, "Tasmania"),
            "primary_cohort_decision": decision, "decision_reason": reason,
            "review_status": review,
            "ala_discovery_crosscheck": "exact_name_hit" if discovery_row else "no_exact_name_hit",
            "ala_accepted_name": discovery_row.get("Species Name", ""),
            "ala_accepted_concept_id": discovery_row.get("Species", ""),
            "query_roles": "|".join(roles),
            "shared_evaluation_eligible": str(shared).lower(),
            "shared_override_basis": override,
            "query_strategy": query_strategy, "query_concepts": _json(query_concepts),
            "accepted_descendants": _json(descendants), "evidence_backed_aliases": _json(aliases),
            "provider_record_deduplication": "occurrenceID required; identical occurrenceID retained once across parent, descendant, and approved-alias branches" if roles else "not_applicable",
            "regional_evidence_ids": _json(evidence_ids),
        })
    manifest = {
        "candidate_frame": {
            "product": "AMTC Australian Mammal Species List", "version": AMTC_VERSION,
            "source_url": "https://australianmammals.org.au/publications/amtc-species-list/",
            "download_sha256": AMTC_SHA256, "species_rows": len(frame),
            "globally_extinct_rows": sum(bool(row["extinct"]) for row in frame),
        },
        "ala_discovery_crosscheck": {
            "role": "cross-check_only_not_completeness_or_eligibility",
            "exact_name_overlap": sum(row["scientific_name"] in discovery for row in frame),
            "amtc_without_exact_discovery_hit": sum(row["scientific_name"] not in discovery for row in frame),
            "discovery_names_absent_from_amtc": sorted(set(discovery) - {str(row["scientific_name"]) for row in frame}),
        },
        "regional_evidence": sources,
        "mainland_donor_bie_evidence": bie_donor_evidence,
        "query_policy": {
            "authority": "Goal011 accepted-concept round-trip plus Goal012 explicit reviewed-union fallback",
            "parent_expansion_assumed": False,
            "aliases": "raw synonym strings are not query-ready; only the Goal012-evidenced Macropus normalized-name path is promoted",
            "provider_record_deduplication": "occurrenceID required, matching Goal012",
        },
        "summary": {
            "rows": len(output),
            "decisions": dict(sorted(Counter(row["primary_cohort_decision"] for row in output).items())),
            "query_role_taxa": sum(bool(row["query_roles"]) for row in output),
            "shared_evaluation_taxa": sum(row["shared_evaluation_eligible"] == "true" for row in output),
            "query_cohort_scope": "conservative_nonrepresentative_feasibility_subset",
            "selection_mechanism": "five approved shared anchors plus Macropus mainland control plus taxa with parsed current VIC/ACT legal-status evidence and selected-IBRA corroboration",
            "known_selection_bias": "current legal-status evidence preferentially identifies threatened/listed taxa and omits many common plausible donors",
            "broad_cohort_representativeness": "unproven",
            "permitted_future_claim": "operational acquisition/support feasibility for the frozen subset only, not all southeastern mammals",
        },
    }
    return output, manifest


def write_taxon_freeze(root: Path) -> dict:
    rows, manifest = build_taxon_freeze(root)
    ledger = root / "metadata/goal040_taxon_query_ledger.csv"
    with ledger.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS, lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
    evidence = root / "metadata/goal040_taxon_evidence_manifest.json"
    evidence.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def validate_taxon_freeze(root: Path) -> dict:
    with (root / "metadata/goal040_taxon_query_ledger.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 416 or list(rows[0]) != LEDGER_FIELDS:
        raise ValueError("AMTC-led ledger schema/frame drift")
    by_name = {row["scientific_name"]: row for row in rows}
    if len(by_name) != 416:
        raise ValueError("duplicate taxon in AMTC-led ledger")
    if sum(row["global_extant_status"] == "no" for row in rows) != 40:
        raise ValueError("AMTC global-extinction classification drift")
    for name in ("Conilurus albipes", "Lagorchestes leporides", "Perameles fasciata"):
        if by_name[name]["global_extant_status"] != "no" or by_name[name]["primary_cohort_decision"] != "exclude":
            raise ValueError(f"globally extinct negative control admitted: {name}")
    if {name for name in ANCHORS if by_name[name]["shared_evaluation_eligible"] != "true"}:
        raise ValueError("approved anchor is not shared-evaluation eligible")
    for name in ("Petaurus breviceps", "Petaurus notatus", "Dasyurus viverrinus", "Thylogale billardierii", "Sarcophilus harrisii", "Macropus giganteus"):
        if by_name[name]["shared_evaluation_eligible"] == "true":
            raise ValueError(f"regional/override negative control admitted to shared evaluation: {name}")
    for row in rows:
        roles = set(row["query_roles"].split("|")) if row["query_roles"] else set()
        if "mainland_donor_pretraining" in roles and row["current_native_extant_mainland_status"] != "yes":
            raise ValueError("mainland donor role lacks affirmative mainland status")
        if roles & {"tasmania_support", "shared_evaluation_candidate"} and row["current_native_extant_tasmania_status"] != "yes":
            raise ValueError("Tasmania/shared role lacks affirmative Tasmania status")
        if row["shared_evaluation_eligible"] == "true" and (
            "shared_evaluation_candidate" not in roles
            or row["current_native_extant_mainland_status"] != "yes"
            or row["current_native_extant_tasmania_status"] != "yes"
        ):
            raise ValueError("shared eligibility lacks both regional statuses and shared role")
        if roles:
            if "unknown" in (row["current_native_extant_mainland_status"], row["current_native_extant_tasmania_status"]):
                raise ValueError("query-role taxon has unresolved regional status")
            concepts = json.loads(row["query_concepts"])
            if not concepts or row["query_strategy"] != "explicit_reviewed_parent_plus_domain_relevant_accepted_descendants_union":
                raise ValueError("query-role taxon lacks reviewed union strategy")
    if sum(bool(row["query_roles"]) for row in rows) != 21:
        raise ValueError("frozen query-role taxon count drift")
    if sum(row["shared_evaluation_eligible"] == "true" for row in rows) != 5:
        raise ValueError("frozen shared-evaluation taxon count drift")
    manifest = json.loads(
        (root / "metadata/goal040_taxon_evidence_manifest.json").read_text(encoding="utf-8")
    )
    if manifest["candidate_frame"]["download_sha256"] != AMTC_SHA256:
        raise ValueError("tracked AMTC authority digest drift")
    if manifest["summary"]["query_cohort_scope"] != "conservative_nonrepresentative_feasibility_subset":
        raise ValueError("frozen-subset inferential scope drift")
    return manifest["summary"]
