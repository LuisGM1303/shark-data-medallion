from __future__ import annotations

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.merge.merger import (
    MergedSpecies,
    _summarize_occurrences,
    merge_species,
)

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


SAMPLE_WIKIPEDIA = {
    "species_key": "carcharodon_carcharias",
    "title": "Great white shark",
    "extract": "The great white shark (Carcharodon carcharias), also known as the white shark, white pointer, or simply great white, is a species of large mackerel shark which can be found in the coastal surface waters of all the major oceans. It is the only known surviving species of its genus Carcharodon.",
    "sections_text": """== Description and morphology ==
The great white shark is a large mackerel shark.

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
Great white sharks are responsible for the most recorded shark attacks on humans.""",
    "page_url": "https://en.wikipedia.org/wiki/Great_white_shark",
}

SAMPLE_TAXONOMY_MATCHED = {
    "species_key": "carcharodon_carcharias",
    "usage_key": 123,
    "scientific_name": "Carcharodon carcharias",
    "canonical_name": "Carcharodon carcharias",
    "rank": "SPECIES",
    "match_type": "EXACT",
    "confidence": 100,
    "kingdom": "Animalia",
    "phylum": "Chordata",
    "class_name": "Chondrichthyes",
}

SAMPLE_TAXONOMY_UNMATCHED = {
    "species_key": "carcharodon_carcharias",
    "usage_key": 123,
    "scientific_name": "Carcharodon carcharias",
    "canonical_name": "Carcharodon carcharias",
    "rank": "SPECIES",
    "match_type": "FUZZY",
    "confidence": 70,
}

SAMPLE_OCCURRENCES = [
    {
        "gbif_id": 1001, "species_key": "carcharodon_carcharias",
        "decimal_latitude": 34.0, "decimal_longitude": -120.0,
        "country": "United States", "event_date": datetime(2020, 6, 15),
        "basis_of_record": "HUMAN_OBSERVATION",
        "iucn_red_list_category": "VULNERABLE",
    },
    {
        "gbif_id": 1002, "species_key": "carcharodon_carcharias",
        "decimal_latitude": -26.0, "decimal_longitude": 15.0,
        "country": "South Africa", "event_date": datetime(2019, 3, 10),
        "basis_of_record": "HUMAN_OBSERVATION",
        "iucn_red_list_category": "VULNERABLE",
    },
    {
        "gbif_id": 1003, "species_key": "carcharodon_carcharias",
        "decimal_latitude": -35.0, "decimal_longitude": 18.0,
        "country": "South Africa", "event_date": datetime(2021, 8, 22),
        "basis_of_record": "OBSERVATION",
        "iucn_red_list_category": "NEAR_THREATENED",
    },
    {
        "gbif_id": 1004, "species_key": "carcharodon_carcharias",
        "decimal_latitude": 40.0, "decimal_longitude": -70.0,
        "country": "United States", "event_date": datetime(2015, 1, 5),
        "basis_of_record": "HUMAN_OBSERVATION",
        "iucn_red_list_category": "VULNERABLE",
    },
]


@test("Merge requires Wikipedia as mandatory pivot (1:1 cardinality per species)")
def test_merge_wikipedia_mandatory():
    result = merge_species(None, SAMPLE_TAXONOMY_MATCHED, [])
    assert result is None, "merge should return None when Wikipedia data is None"

    result = merge_species(SAMPLE_WIKIPEDIA, SAMPLE_TAXONOMY_MATCHED, [])
    assert result is not None, "merge should return MergedSpecies when Wikipedia is provided"
    assert result.wikipedia_title == "Great white shark"


@test("Species without valid Wikipedia are not added to species_catalog")
def test_no_wikipedia_no_catalog():
    result = merge_species(None, SAMPLE_TAXONOMY_MATCHED, SAMPLE_OCCURRENCES)
    assert result is None

    result = merge_species(None, None, [])
    assert result is None


@test("GBIF never introduces a species_key that doesn't exist in Wikipedia")
def test_gbif_cannot_introduce():
    result = merge_species(None, SAMPLE_TAXONOMY_MATCHED, SAMPLE_OCCURRENCES)
    assert result is None

    result = merge_species(None, None, SAMPLE_OCCURRENCES)
    assert result is None


@test("GBIF Taxonomy joined by species_key only when match_type is EXACT")
def test_gbif_taxonomy_exact_join():
    result = merge_species(SAMPLE_WIKIPEDIA, SAMPLE_TAXONOMY_MATCHED, [])
    assert result is not None
    assert result.taxonomy_status == "MATCHED"
    assert result.kingdom == "Animalia"
    assert result.phylum == "Chordata"
    assert result.class_name == "Chondrichthyes"
    assert result.rank == "SPECIES"


@test("Non-EXACT GBIF Taxonomy results in UNMATCHED status (species still valid via Wikipedia)")
def test_non_exact_taxonomy_unmatched():
    result = merge_species(SAMPLE_WIKIPEDIA, SAMPLE_TAXONOMY_UNMATCHED, [])
    assert result is not None
    assert result.taxonomy_status == "UNMATCHED"
    assert result.kingdom is None
    assert result.phylum is None
    assert result.class_name is None
    assert result.rank is None
    assert result.wikipedia_title == "Great white shark"


@test("GBIF Occurrence aggregated 1:N -> 1:1 summary per species")
def test_occurrence_aggregation():
    result = merge_species(SAMPLE_WIKIPEDIA, SAMPLE_TAXONOMY_MATCHED, SAMPLE_OCCURRENCES)
    assert result is not None
    assert result.n_occurrences_validas == 4
    assert isinstance(result.paises, list)
    assert len(result.paises) == 2
    assert result.paises[0] == "United States"


@test("GBIFOccurrenceSummary includes n_occurrences_validas count")
def test_summary_counts():
    summary = _summarize_occurrences(SAMPLE_OCCURRENCES)
    assert summary["n_occurrences_validas"] == 4

    summary = _summarize_occurrences([])
    assert summary["n_occurrences_validas"] == 0


@test("GBIFOccurrenceSummary paises ordered by frequency descending")
def test_paises_frequency():
    summary = _summarize_occurrences(SAMPLE_OCCURRENCES)
    assert summary["paises"] == ["United States", "South Africa"]

    summary = _summarize_occurrences([])
    assert summary["paises"] == []

    single_occ = [SAMPLE_OCCURRENCES[0]]
    summary = _summarize_occurrences(single_occ)
    assert summary["paises"] == ["United States"]


@test("GBIFOccurrenceSummary anio_min and anio_max from occurrence date range")
def test_anio_range():
    summary = _summarize_occurrences(SAMPLE_OCCURRENCES)
    assert summary["anio_min"] == 2015
    assert summary["anio_max"] == 2021

    summary = _summarize_occurrences([])
    assert summary["anio_min"] is None
    assert summary["anio_max"] is None

    no_dates = [
        {
            "gbif_id": 2001, "species_key": "test",
            "decimal_latitude": 0.0, "decimal_longitude": 0.0,
            "basis_of_record": "HUMAN_OBSERVATION",
        }
    ]
    summary = _summarize_occurrences(no_dates)
    assert summary["anio_min"] is None
    assert summary["anio_max"] is None


@test("GBIFOccurrenceSummary iucn_red_list_category uses mode (most frequent)")
def test_iucn_mode():
    summary = _summarize_occurrences(SAMPLE_OCCURRENCES)
    assert summary["iucn_red_list_category"] == "VULNERABLE"

    summary = _summarize_occurrences([])
    assert summary["iucn_red_list_category"] is None

    tied_occurrences = [
        dict(SAMPLE_OCCURRENCES[0]),
        dict(SAMPLE_OCCURRENCES[1]),
        dict(SAMPLE_OCCURRENCES[2]),
    ]
    tied_occurrences[1]["iucn_red_list_category"] = "NEAR_THREATENED"
    summary = _summarize_occurrences(tied_occurrences)
    assert summary["iucn_red_list_category"] is not None


@test("Zero valid occurrences results in GBIF_AUGMENTATION_EMPTY (not an error)")
def test_augmentation_empty():
    result = merge_species(SAMPLE_WIKIPEDIA, SAMPLE_TAXONOMY_MATCHED, [])
    assert result is not None
    assert result.augmentation_status == "GBIF_AUGMENTATION_EMPTY"
    assert result.n_occurrences_validas == 0
    assert result.paises == []
    assert result.anio_min is None
    assert result.anio_max is None

    result_with_occ = merge_species(SAMPLE_WIKIPEDIA, SAMPLE_TAXONOMY_MATCHED, SAMPLE_OCCURRENCES)
    assert result_with_occ is not None
    assert result_with_occ.augmentation_status == "OK"
    assert result_with_occ.n_occurrences_validas == 4


@test("Merge output record contains all required fields")
def test_merge_output_fields():
    result = merge_species(SAMPLE_WIKIPEDIA, SAMPLE_TAXONOMY_MATCHED, SAMPLE_OCCURRENCES)
    assert result is not None

    assert result.species_key == "carcharodon_carcharias"
    assert result.wikipedia_title == "Great white shark"
    assert len(result.extract) > 0
    assert len(result.sections_text) > 0
    assert result.kingdom == "Animalia"
    assert result.phylum == "Chordata"
    assert result.class_name == "Chondrichthyes"
    assert result.rank == "SPECIES"
    assert result.taxonomy_status == "MATCHED"
    assert result.n_occurrences_validas == 4
    assert len(result.paises) > 0
    assert result.anio_min == 2015
    assert result.anio_max == 2021
    assert result.iucn_red_list_category is not None
    assert result.augmentation_status == "OK"

    result_none = merge_species(SAMPLE_WIKIPEDIA, None, [])
    assert result_none is not None
    assert result_none.taxonomy_status == "UNMATCHED"
    assert result_none.augmentation_status == "GBIF_AUGMENTATION_EMPTY"


@test("Merge handles species where both GBIF taxonomy AND occurrences are absent")
def test_merge_no_gbif_at_all():
    result = merge_species(SAMPLE_WIKIPEDIA, None, [])
    assert result is not None
    assert result.species_key == "carcharodon_carcharias"
    assert result.wikipedia_title == "Great white shark"
    assert result.taxonomy_status == "UNMATCHED"
    assert result.kingdom is None
    assert result.phylum is None
    assert result.class_name is None
    assert result.rank is None
    assert result.augmentation_status == "GBIF_AUGMENTATION_EMPTY"
    assert result.n_occurrences_validas == 0
    assert result.paises == []
    assert result.anio_min is None
    assert result.anio_max is None
    assert result.iucn_red_list_category is None


if __name__ == "__main__":
    n = len([k for k in dir() if k.startswith("test_") and callable(locals()[k])])
    print(f"Running {n} Merge layer tests...\n")

    print(f"\nResults: {PASSED} passed, {FAILED} failed")
    if ERRORS:
        print("\nErrors:")
        for name, err in ERRORS:
            print(f"  {name}: {err}")
    sys.exit(0 if FAILED == 0 else 1)
