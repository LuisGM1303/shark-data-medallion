"""Gold layer models: Species (parent), SpeciesChunk (child), SpeciesMetadata."""

from typing import Optional

from pydantic import BaseModel


class Species(BaseModel):
    species_key: str
    identity: Optional[str] = None
    taxonomy: Optional[str] = None
    morphology: Optional[str] = None
    distribution: Optional[str] = None
    habitat: Optional[str] = None
    behavior: Optional[str] = None
    diet: Optional[str] = None
    reproduction: Optional[str] = None
    conservation: Optional[str] = None
    human_interaction: Optional[str] = None
    references: Optional[str] = None
    multimedia: Optional[str] = None


class SpeciesChunk(BaseModel):
    chunk_id: str
    species_key: str
    section: str
    text: str


class SpeciesMetadata(BaseModel):
    species_key: str
    kingdom: Optional[str] = None
    phylum: Optional[str] = None
    class_name: Optional[str] = None
    rank: Optional[str] = None
    taxonomy_status: str
    iucn_red_list_category: Optional[str] = None
    paises: list[str] = []
    anio_min: Optional[int] = None
    anio_max: Optional[int] = None
    n_occurrences_validas: int = 0
    augmentation_status: str
