"""Gold layer: chunking, embeddings, FAISS index, and search."""

from typing import Optional

import numpy as np


def build_species_from_merged(merged: dict) -> dict:
    raise NotImplementedError


def chunk_species(species: dict) -> list[dict]:
    raise NotImplementedError


def build_metadata(species: dict, merged: dict) -> dict:
    raise NotImplementedError


def embed_chunks(chunks: list[dict]) -> np.ndarray:
    raise NotImplementedError


def build_faiss_index(embeddings: np.ndarray) -> object:
    raise NotImplementedError


def save_index(index: object, metadata: list[dict]) -> None:
    raise NotImplementedError


def search(
    query: str,
    top_k: int = 5,
    filtro_taxonomia: Optional[dict] = None,
    filtro_iucn: Optional[str] = None,
    filtro_pais: Optional[str] = None,
) -> list[dict]:
    raise NotImplementedError
