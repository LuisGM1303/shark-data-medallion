"""Gold models: canonical Species (parent) and SpeciesChunk (child).

The 12 canonical sections are the knowledge boundaries used for semantic
chunking. SpeciesMetadata is intentionally NOT a persisted standalone entity
in v2: its fields are denormalized into gold.species_chunks.
"""

from typing import Optional

from pydantic import BaseModel

CANONICAL_SECTIONS = [
    "Identity", "Taxonomy", "Morphology", "Distribution", "Habitat",
    "Behavior", "Diet", "Reproduction", "Conservation", "Human Interaction",
    "References", "Multimedia",
]

SECTION_ATTR = {
    "Identity": "identity",
    "Taxonomy": "taxonomy",
    "Morphology": "morphology",
    "Distribution": "distribution",
    "Habitat": "habitat",
    "Behavior": "behavior",
    "Diet": "diet",
    "Reproduction": "reproduction",
    "Conservation": "conservation",
    "Human Interaction": "human_interaction",
    "References": "references",
    "Multimedia": "multimedia",
}


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
    document_text: str


class SpeciesChunk(BaseModel):
    chunk_id: str
    species_key: str
    section: str
    chunk_ordinal: int
    text: str
