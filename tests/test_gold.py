from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.gold.indexer import (
    CANONICAL_SECTIONS,
    _SECTION_KEYWORDS,
    _match_section,
    build_species_from_merged,
    chunk_species,
    build_metadata,
)
from src.gold.models import Species, SpeciesChunk, SpeciesMetadata

PASSED = 0
FAILED = 0
ERRORS = []


def test(name: str):
    def decorator(fn):
        global PASSED, FAILED
        try:
            fn()
            PASSED += 1
            print(f"  PASS: {name}")
        except Exception as e:
            FAILED += 1
            ERRORS.append((name, str(e)))
            print(f"  FAIL: {name} - {e}")
        return fn
    return decorator


SAMPLE_MERGED_MATCHED = {
    "species_key": "carcharodon_carcharias",
    "wikipedia_title": "Great white shark",
    "extract": "The great white shark (Carcharodon carcharias), also known as the white shark, white pointer, or simply great white, is a species of large mackerel shark which can be found in the coastal surface waters of all the major oceans. It is the only known surviving species of its genus Carcharodon.",
    "sections_text": """== Description and morphology ==
The great white shark has a robust, large, conical snout.

== Distribution and habitat ==
Great white sharks are found in coastal waters worldwide.

== Behavior ==
Great white sharks are apex predators.

== Diet and feeding ==
The great white shark's diet includes fish, seals, and sea lions.

== Reproduction ==
Great white sharks are ovoviviparous.

== Conservation status ==
The great white shark is listed as vulnerable.

== Human interaction ==
Great white sharks are responsible for the most recorded shark attacks on humans.

== References ==
1. Compagno, L.J.V. (1984). Sharks of the World.

== Gallery ==
Great white shark breaching. Credit: National Geographic.""",
    "page_url": "https://en.wikipedia.org/wiki/Great_white_shark",
    "kingdom": "Animalia",
    "phylum": "Chordata",
    "class_name": "Chondrichthyes",
    "rank": "SPECIES",
    "taxonomy_status": "MATCHED",
    "n_occurrences_validas": 4,
    "paises": ["United States", "South Africa"],
    "anio_min": 2015,
    "anio_max": 2021,
    "iucn_red_list_category": "VULNERABLE",
    "augmentation_status": "OK",
}

SAMPLE_MERGED_UNMATCHED = {
    "species_key": "carcharodon_carcharias",
    "wikipedia_title": "Great white shark",
    "extract": "The great white shark (Carcharodon carcharias), also known as the white shark.",
    "sections_text": "",
    "page_url": "https://en.wikipedia.org/wiki/Great_white_shark",
    "taxonomy_status": "UNMATCHED",
    "n_occurrences_validas": 0,
    "paises": [],
    "augmentation_status": "GBIF_AUGMENTATION_EMPTY",
}

SAMPLE_MERGED_MINIMAL = {
    "species_key": "prionace_glauca",
    "wikipedia_title": "Blue shark",
    "extract": "The blue shark (Prionace glauca) is a species of requiem shark.",
    "sections_text": "== Habitat ==\nBlue sharks prefer cooler waters.\n\n== Behavior ==\nThey are known for their migratory patterns.",
    "page_url": "https://en.wikipedia.org/wiki/Blue_shark",
    "taxonomy_status": "UNMATCHED",
    "n_occurrences_validas": 0,
    "paises": [],
    "augmentation_status": "GBIF_AUGMENTATION_EMPTY",
}


@test("Species model has Identity section populated from Wikipedia")
def test_species_identity():
    species = build_species_from_merged(SAMPLE_MERGED_MATCHED)
    assert species["identity"] is not None
    assert "Great white shark" in species["identity"]
    assert "carcharodon_carcharias" in species["identity"]

    minimal = build_species_from_merged(SAMPLE_MERGED_MINIMAL)
    assert minimal["identity"] is not None
    assert "Blue shark" in minimal["identity"]


@test("Species model has Taxonomy section from GBIF merge fields")
def test_species_taxonomy():
    species = build_species_from_merged(SAMPLE_MERGED_MATCHED)
    assert species["taxonomy"] is not None
    assert "Animalia" in species["taxonomy"]
    assert "Chordata" in species["taxonomy"]
    assert "Chondrichthyes" in species["taxonomy"]
    assert "SPECIES" in species["taxonomy"]

    unmatched = build_species_from_merged(SAMPLE_MERGED_UNMATCHED)
    assert unmatched["taxonomy"] is None


@test("Species model has Morphology section extracted from Wikipedia sections_text")
def test_species_morphology():
    species = build_species_from_merged(SAMPLE_MERGED_MATCHED)
    assert species["morphology"] is not None
    assert "conical snout" in species["morphology"]

    minimal = build_species_from_merged(SAMPLE_MERGED_MINIMAL)
    assert minimal["morphology"] is None


@test("Species model has Distribution section extracted from Wikipedia")
def test_species_distribution():
    species = build_species_from_merged(SAMPLE_MERGED_MATCHED)
    assert species["distribution"] is not None
    assert "coastal waters worldwide" in species["distribution"]

    minimal = build_species_from_merged(SAMPLE_MERGED_MINIMAL)
    assert minimal["distribution"] is None


@test("Species model has Habitat section extracted from Wikipedia")
def test_species_habitat():
    minimal = build_species_from_merged(SAMPLE_MERGED_MINIMAL)
    assert minimal["habitat"] is not None
    assert "cooler waters" in minimal["habitat"]


@test("Species model has Behavior section extracted from Wikipedia")
def test_species_behavior():
    species = build_species_from_merged(SAMPLE_MERGED_MATCHED)
    assert species["behavior"] is not None
    assert "apex predators" in species["behavior"]

    minimal = build_species_from_merged(SAMPLE_MERGED_MINIMAL)
    assert minimal["behavior"] is not None
    assert "migratory patterns" in minimal["behavior"]


@test("Species model has Diet section extracted from Wikipedia")
def test_species_diet():
    species = build_species_from_merged(SAMPLE_MERGED_MATCHED)
    assert species["diet"] is not None
    assert "seals" in species["diet"]

    minimal = build_species_from_merged(SAMPLE_MERGED_MINIMAL)
    assert minimal["diet"] is None


@test("Species model has Reproduction section extracted from Wikipedia")
def test_species_reproduction():
    species = build_species_from_merged(SAMPLE_MERGED_MATCHED)
    assert species["reproduction"] is not None
    assert "ovoviviparous" in species["reproduction"]

    minimal = build_species_from_merged(SAMPLE_MERGED_MINIMAL)
    assert minimal["reproduction"] is None


@test("Species model has Conservation section extracted from Wikipedia")
def test_species_conservation():
    species = build_species_from_merged(SAMPLE_MERGED_MATCHED)
    assert species["conservation"] is not None
    assert "vulnerable" in species["conservation"]

    minimal = build_species_from_merged(SAMPLE_MERGED_MINIMAL)
    assert minimal["conservation"] is None


@test("Species model has Human Interaction section extracted from Wikipedia")
def test_species_human_interaction():
    species = build_species_from_merged(SAMPLE_MERGED_MATCHED)
    assert species["human_interaction"] is not None
    assert "shark attacks" in species["human_interaction"]

    minimal = build_species_from_merged(SAMPLE_MERGED_MINIMAL)
    assert minimal["human_interaction"] is None


@test("Species model has References section extracted from Wikipedia")
def test_species_references():
    species = build_species_from_merged(SAMPLE_MERGED_MATCHED)
    assert species["references"] is not None
    assert "Compagno" in species["references"]

    minimal = build_species_from_merged(SAMPLE_MERGED_MINIMAL)
    assert minimal["references"] is None


@test("Species model has Multimedia section extracted from Wikipedia")
def test_species_multimedia():
    species = build_species_from_merged(SAMPLE_MERGED_MATCHED)
    assert species["multimedia"] is not None
    assert "National Geographic" in species["multimedia"]

    minimal = build_species_from_merged(SAMPLE_MERGED_MINIMAL)
    assert minimal["multimedia"] is None


@test("All 12 canonical sections are present in Species model (some may be None)")
def test_all_canonical_sections_present():
    species = build_species_from_merged(SAMPLE_MERGED_MATCHED)
    for sec in CANONICAL_SECTIONS:
        attr_map = {
            "Identity": "identity", "Taxonomy": "taxonomy", "Morphology": "morphology",
            "Distribution": "distribution", "Habitat": "habitat", "Behavior": "behavior",
            "Diet": "diet", "Reproduction": "reproduction", "Conservation": "conservation",
            "Human Interaction": "human_interaction", "References": "references", "Multimedia": "multimedia",
        }
        attr = attr_map[sec]
        assert attr in species, f"Missing section: {sec} ({attr})"
        assert species[attr] is None or isinstance(species[attr], str), f"Section {sec} should be str or None"

    assert len(CANONICAL_SECTIONS) == 12


@test("SpeciesChunk model has chunk_id in format {species_key}__{section}__{n}")
def test_chunk_id_format():
    chunk = SpeciesChunk(
        chunk_id="carcharodon_carcharias__Habitat__0",
        species_key="carcharodon_carcharias",
        section="Habitat",
        text="Sharks live in oceans.",
    )
    assert chunk.chunk_id == "carcharodon_carcharias__Habitat__0"
    assert "__" in chunk.chunk_id
    parts = chunk.chunk_id.split("__")
    assert len(parts) == 3
    assert parts[0] == "carcharodon_carcharias"
    assert parts[1] == "Habitat"
    assert parts[2].isdigit()


@test("SpeciesChunk model has species_key foreign key field")
def test_chunk_species_key():
    chunk = SpeciesChunk(
        chunk_id="test__Identity__0",
        species_key="carcharodon_carcharias",
        section="Identity",
        text="Test",
    )
    assert chunk.species_key == "carcharodon_carcharias"
    assert isinstance(chunk.species_key, str)


@test("SpeciesChunk model has section name matching canonical sections")
def test_chunk_section_name():
    chunk = SpeciesChunk(
        chunk_id="test__Habitat__0",
        species_key="test",
        section="Habitat",
        text="Test habitat.",
    )
    assert chunk.section == "Habitat"
    assert chunk.section in CANONICAL_SECTIONS


@test("SpeciesChunk model has text content field")
def test_chunk_text():
    chunk = SpeciesChunk(
        chunk_id="test__Identity__0",
        species_key="test",
        section="Identity",
        text="Test content.",
    )
    assert chunk.text == "Test content."
    assert len(chunk.text) > 0


@test("Chunking produces semantic chunks per canonical section (not fixed-size)")
def test_chunking_semantic():
    species = build_species_from_merged(SAMPLE_MERGED_MATCHED)
    chunks = chunk_species(species)

    assert len(chunks) > 0
    seen_sections = set()
    for c in chunks:
        assert c["section"] in CANONICAL_SECTIONS
        assert c["species_key"] == "carcharodon_carcharias"
        assert c["chunk_id"].startswith("carcharodon_carcharias__")
        assert len(c["text"]) > 0
        seen_sections.add(c["section"])

    non_null_sections = [s for s in CANONICAL_SECTIONS if species.get({
        "Identity": "identity", "Taxonomy": "taxonomy", "Morphology": "morphology",
        "Distribution": "distribution", "Habitat": "habitat", "Behavior": "behavior",
        "Diet": "diet", "Reproduction": "reproduction", "Conservation": "conservation",
        "Human Interaction": "human_interaction", "References": "references", "Multimedia": "multimedia",
    }.get(s, s))]

    assert len(chunks) >= len(non_null_sections)


@test("SpeciesMetadata model has all filter fields for structured search")
def test_metadata_fields():
    species = build_species_from_merged(SAMPLE_MERGED_MATCHED)
    meta = build_metadata(species, SAMPLE_MERGED_MATCHED)

    assert "species_key" in meta
    assert "kingdom" in meta
    assert "phylum" in meta
    assert "class_name" in meta
    assert "rank" in meta
    assert "taxonomy_status" in meta
    assert "iucn_red_list_category" in meta
    assert "paises" in meta
    assert "anio_min" in meta
    assert "anio_max" in meta
    assert "n_occurrences_validas" in meta
    assert "augmentation_status" in meta


@test("SpeciesMetadata taxonomy_status is 'MATCHED' or 'UNMATCHED'")
def test_metadata_taxonomy_status():
    species_matched = build_species_from_merged(SAMPLE_MERGED_MATCHED)
    meta_matched = build_metadata(species_matched, SAMPLE_MERGED_MATCHED)
    assert meta_matched["taxonomy_status"] == "MATCHED"

    species_unmatched = build_species_from_merged(SAMPLE_MERGED_UNMATCHED)
    meta_unmatched = build_metadata(species_unmatched, SAMPLE_MERGED_UNMATCHED)
    assert meta_unmatched["taxonomy_status"] == "UNMATCHED"


@test("SpeciesMetadata augmentation_status is 'OK' or 'GBIF_AUGMENTATION_EMPTY'")
def test_metadata_augmentation_status():
    species_ok = build_species_from_merged(SAMPLE_MERGED_MATCHED)
    meta_ok = build_metadata(species_ok, SAMPLE_MERGED_MATCHED)
    assert meta_ok["augmentation_status"] == "OK"

    species_empty = build_species_from_merged(SAMPLE_MERGED_UNMATCHED)
    meta_empty = build_metadata(species_empty, SAMPLE_MERGED_UNMATCHED)
    assert meta_empty["augmentation_status"] == "GBIF_AUGMENTATION_EMPTY"


@test("SpeciesMetadata paises is a list of strings (countries ordered by frequency)")
def test_metadata_paises():
    species = build_species_from_merged(SAMPLE_MERGED_MATCHED)
    meta = build_metadata(species, SAMPLE_MERGED_MATCHED)
    assert isinstance(meta["paises"], list)
    assert len(meta["paises"]) == 2
    assert meta["paises"][0] == "United States"
    assert meta["paises"][1] == "South Africa"
    for p in meta["paises"]:
        assert isinstance(p, str)


@test("Species model serializes to JSON and back without data loss")
def test_species_serialization():
    species = Species(
        species_key="carcharodon_carcharias",
        identity="Species: Great white shark",
        taxonomy="kingdom: Animalia; phylum: Chordata",
        morphology="Large conical snout.",
        distribution="Coastal waters worldwide.",
        habitat="Coastal and offshore waters.",
        behavior="Apex predator.",
        diet="Fish, seals, sea lions.",
        reproduction="Ovoviviparous.",
        conservation="Vulnerable.",
        human_interaction="Shark attacks on humans.",
        references="Compagno (1984).",
        multimedia="Images available.",
    )
    json_str = species.model_dump_json()
    restored = Species.model_validate_json(json_str)
    assert restored.species_key == species.species_key
    assert restored.identity == species.identity
    assert restored.taxonomy == species.taxonomy
    assert restored.morphology == species.morphology
    assert restored.distribution == species.distribution
    assert restored.habitat == species.habitat
    assert restored.behavior == species.behavior
    assert restored.diet == species.diet
    assert restored.reproduction == species.reproduction
    assert restored.conservation == species.conservation
    assert restored.human_interaction == species.human_interaction
    assert restored.references == species.references
    assert restored.multimedia == species.multimedia


if __name__ == "__main__":
    n = len([k for k in dir() if k.startswith("test_") and callable(locals()[k])])
    print(f"Running {n} Gold layer tests...\n")

    print(f"\nResults: {PASSED} passed, {FAILED} failed")
    if ERRORS:
        print("\nErrors:")
        for name, err in ERRORS:
            print(f"  {name}: {err}")
    sys.exit(0 if FAILED == 0 else 1)
