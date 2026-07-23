"""Pydantic v2 models for Silver layer validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class WikipediaPage(BaseModel):
    species_key: str
    title: str
    resolved_via: str
    extract: str
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
    decimal_latitude: float
    decimal_longitude: float
    country: Optional[str] = None
    event_date: Optional[datetime] = None
    basis_of_record: str
    iucn_red_list_category: Optional[str] = None
    coordinate_uncertainty_m: Optional[float] = None
