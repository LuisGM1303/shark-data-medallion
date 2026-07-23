"""Merge layer: Wikipedia pivot + GBIF augmentation."""

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


def merge_species(wikipedia_data: dict, gbif_taxonomy: dict | None, gbif_occurrences: list[dict]) -> MergedSpecies:
    raise NotImplementedError
