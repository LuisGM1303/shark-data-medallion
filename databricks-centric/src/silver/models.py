"""Pydantic v2 models for Silver layer validation (preserved from v1)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class WikipediaPage(BaseModel):
    species_key: str
    title: str = Field(min_length=1)
    resolved_via: str
    extract: str = Field(min_length=50)
    sections_text: str
    page_url: str
    is_disambiguation: bool = False


class GBIFTaxonomy(BaseModel):
    species_key: str
    usage_key: int
    scientific_name: str
    canonical_name: str
    rank: str
    match_type: str
    confidence: int
    kingdom: Optional[str] = None
    phylum: Optional[str] = None
    class_name: Optional[str] = None


class GBIFOccurrence(BaseModel):
    gbif_id: int
    species_key: str
    decimal_latitude: float = Field(ge=-90, le=90)
    decimal_longitude: float = Field(ge=-180, le=180)
    country: Optional[str] = None
    event_date: Optional[datetime] = None
    basis_of_record: str
    iucn_red_list_category: Optional[str] = None
    coordinate_uncertainty_m: Optional[float] = None
