from __future__ import annotations

from collections import Counter
from typing import Optional

from pydantic import BaseModel


class GBIFOccurrenceSummary(BaseModel):
    species_key: str
    n_occurrences_validas: int
    paises: list[str]
    anio_min: Optional[int] = None
    anio_max: Optional[int] = None
    iucn_red_list_category: Optional[str] = None


class MergedSpecies(BaseModel):
    species_key: str
    wikipedia_title: str
    extract: str
    sections_text: str
    kingdom: Optional[str] = None
    phylum: Optional[str] = None
    class_name: Optional[str] = None
    rank: Optional[str] = None
    taxonomy_status: str
    n_occurrences_validas: int
    paises: list[str]
    anio_min: Optional[int] = None
    anio_max: Optional[int] = None
    iucn_red_list_category: Optional[str] = None
    augmentation_status: str


def _summarize_occurrences(occurrences: list[dict]) -> dict:
    if not occurrences:
        return {
            "n_occurrences_validas": 0,
            "paises": [],
            "anio_min": None,
            "anio_max": None,
            "iucn_red_list_category": None,
        }

    country_counter: Counter = Counter()
    iucn_list: list[tuple[str, str]] = []
    years: list[int] = []

    for occ in occurrences:
        country = occ.get("country")
        if country:
            country_counter[country] += 1

        iucn = occ.get("iucn_red_list_category")
        if iucn:
            event_date = occ.get("event_date")
            iucn_list.append((iucn, event_date or ""))

        event_date = occ.get("event_date")
        if event_date and hasattr(event_date, "year"):
            years.append(event_date.year)

    paises = [c for c, _ in country_counter.most_common()]

    iucn_mode = None
    if iucn_list:
        iucn_counter: Counter = Counter(i for i, _ in iucn_list)
        max_count = max(iucn_counter.values())
        tied = [i for i, c in iucn_counter.items() if c == max_count]
        if len(tied) == 1:
            iucn_mode = tied[0]
        else:
            iucn_mode = max(
                tied,
                key=lambda x: max(
                    (d for i, d in iucn_list if i == x and d),
                    default="",
                ),
            )

    return {
        "n_occurrences_validas": len(occurrences),
        "paises": paises,
        "anio_min": min(years) if years else None,
        "anio_max": max(years) if years else None,
        "iucn_red_list_category": iucn_mode,
    }


def merge_species(
    wikipedia_data: dict | None,
    gbif_taxonomy: dict | None,
    gbif_occurrences: list[dict],
) -> MergedSpecies | None:
    if not wikipedia_data:
        return None

    species_key = wikipedia_data.get("species_key", "")

    tax_status = "UNMATCHED"
    kingdom = None
    phylum = None
    class_name = None
    rank = None

    if gbif_taxonomy:
        mt = gbif_taxonomy.get("match_type", "")
        if mt == "EXACT":
            tax_status = "MATCHED"
            kingdom = gbif_taxonomy.get("kingdom")
            phylum = gbif_taxonomy.get("phylum")
            class_name = gbif_taxonomy.get("class_name")
            rank = gbif_taxonomy.get("rank")

    occ_summary = _summarize_occurrences(gbif_occurrences or [])
    aug_status = "OK" if occ_summary["n_occurrences_validas"] > 0 else "GBIF_AUGMENTATION_EMPTY"

    return MergedSpecies(
        species_key=species_key,
        wikipedia_title=wikipedia_data.get("title", ""),
        extract=wikipedia_data.get("extract", ""),
        sections_text=wikipedia_data.get("sections_text", ""),
        kingdom=kingdom,
        phylum=phylum,
        class_name=class_name,
        rank=rank,
        taxonomy_status=tax_status,
        n_occurrences_validas=occ_summary["n_occurrences_validas"],
        paises=occ_summary["paises"],
        anio_min=occ_summary["anio_min"],
        anio_max=occ_summary["anio_max"],
        iucn_red_list_category=occ_summary["iucn_red_list_category"],
        augmentation_status=aug_status,
    )
