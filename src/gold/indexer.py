from __future__ import annotations

import os
import re
from typing import Optional

import faiss
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

CANONICAL_SECTIONS = [
    "Identity", "Taxonomy", "Morphology", "Distribution", "Habitat",
    "Behavior", "Diet", "Reproduction", "Conservation", "Human Interaction",
    "References", "Multimedia",
]

_model: SentenceTransformer | None = None

_SECTION_KEYWORDS: dict[str, list[str]] = {
    "Identity": ["identity"],
    "Taxonomy": ["taxonomy", "classification"],
    "Morphology": ["morphology", "description", "anatomy", "appearance"],
    "Distribution": ["distribution", "range", "geographic"],
    "Habitat": ["habitat"],
    "Behavior": ["behavior", "behaviour"],
    "Diet": ["diet", "feeding", "food", "prey", "foraging"],
    "Reproduction": ["reproduction", "breeding", "mating", "life cycle"],
    "Conservation": ["conservation", "threats", "endangered", "status", "population"],
    "Human Interaction": ["human interaction", "shark attack", "human"],
    "References": ["references", "citations", "further reading", "external links"],
    "Multimedia": ["multimedia", "gallery", "media"],
}


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("BAAI/bge-small-en-v1.5")
    return _model


def _match_section(section_name: str) -> str | None:
    sl = section_name.lower().strip()
    for canonical, keywords in _SECTION_KEYWORDS.items():
        for kw in keywords:
            if kw in sl:
                return canonical
    return None


def build_species_from_merged(merged: dict) -> dict:
    species_key = merged.get("species_key", "")
    sciname = merged.get("wikipedia_title", "")
    sections_text = merged.get("sections_text", "")

    sections: dict[str, str | None] = {s: None for s in CANONICAL_SECTIONS}
    sections["Identity"] = f"Species: {sciname} ({species_key})"

    tax_status = merged.get("taxonomy_status", "UNMATCHED")
    if tax_status == "MATCHED":
        parts = []
        for k in ["kingdom", "phylum", "class_name", "rank"]:
            v = merged.get(k)
            if v:
                parts.append(f"{k}: {v}")
        sections["Taxonomy"] = "; ".join(parts) if parts else None

    section_pattern = re.compile(r"^==+\s*(.+?)\s*==+", re.MULTILINE)
    current_section = None
    current_content: list[str] = []
    section_map: dict[str, list[str]] = {}

    for line in sections_text.split("\n"):
        m = section_pattern.match(line)
        if m:
            if current_section and current_content:
                sec_name = current_section.strip()
                sec_map_key = _match_section(sec_name)
                if sec_map_key:
                    section_map.setdefault(sec_map_key, []).append("\n".join(current_content).strip())
            current_section = m.group(1)
            current_content = []
        elif current_section:
            current_content.append(line)

    if current_section and current_content:
        sec_name = current_section.strip()
        sec_map_key = _match_section(sec_name)
        if sec_map_key:
            section_map.setdefault(sec_map_key, []).append("\n".join(current_content).strip())

    extract = merged.get("extract", "")
    for sec in CANONICAL_SECTIONS:
        if sec == "Identity":
            continue
        if sec == "Taxonomy" and sections["Taxonomy"]:
            continue
        if sec in section_map:
            content = "\n".join(section_map[sec]).strip()
            if content:
                sections[sec] = content

    species_dict: dict = {"species_key": species_key}
    attr_map = {
        "Identity": "identity", "Taxonomy": "taxonomy", "Morphology": "morphology",
        "Distribution": "distribution", "Habitat": "habitat", "Behavior": "behavior",
        "Diet": "diet", "Reproduction": "reproduction", "Conservation": "conservation",
        "Human Interaction": "human_interaction", "References": "references", "Multimedia": "multimedia",
    }
    for canonical, attr in attr_map.items():
        species_dict[attr] = sections.get(canonical)

    return species_dict


def chunk_species(species: dict) -> list[dict]:
    species_key = species.get("species_key", "")
    chunks: list[dict] = []

    attr_map = {
        "identity": "Identity", "taxonomy": "Taxonomy", "morphology": "Morphology",
        "distribution": "Distribution", "habitat": "Habitat", "behavior": "Behavior",
        "diet": "Diet", "reproduction": "Reproduction", "conservation": "Conservation",
        "human_interaction": "Human Interaction", "references": "References", "multimedia": "Multimedia",
    }

    for attr, canonical_name in attr_map.items():
        content = species.get(attr)
        if content and isinstance(content, str) and len(content.strip()) > 0:
            chunk_id = f"{species_key}__{canonical_name}__0"
            chunks.append({
                "chunk_id": chunk_id,
                "species_key": species_key,
                "section": canonical_name,
                "text": content.strip(),
            })

    return chunks


def build_metadata(species: dict, merged: dict) -> dict:
    return {
        "species_key": species.get("species_key", ""),
        "kingdom": merged.get("kingdom"),
        "phylum": merged.get("phylum"),
        "class_name": merged.get("class_name"),
        "rank": merged.get("rank"),
        "taxonomy_status": merged.get("taxonomy_status", "UNMATCHED"),
        "iucn_red_list_category": merged.get("iucn_red_list_category"),
        "paises": merged.get("paises", []),
        "anio_min": merged.get("anio_min"),
        "anio_max": merged.get("anio_max"),
        "n_occurrences_validas": merged.get("n_occurrences_validas", 0),
        "augmentation_status": merged.get("augmentation_status", "GBIF_AUGMENTATION_EMPTY"),
    }


def embed_chunks(chunks: list[dict]) -> np.ndarray:
    if not chunks:
        return np.array([], dtype=np.float32)
    model = _get_model()
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(texts, normalize_embeddings=True)
    return np.array(embeddings, dtype=np.float32)


def build_faiss_index(embeddings: np.ndarray) -> faiss.Index:
    if embeddings.size == 0:
        return faiss.IndexHNSWFlat(384, 32)
    dim = embeddings.shape[1]
    index = faiss.IndexHNSWFlat(dim, 32)
    index.add(embeddings)
    return index


def save_index(index: faiss.Index, chunks: list[dict]) -> None:
    os.makedirs("data/gold/faiss_index", exist_ok=True)
    faiss.write_index(index, "data/gold/faiss_index/index.faiss")

    index_meta = []
    chunk_records = []
    for i, chunk in enumerate(chunks):
        index_meta.append({
            "faiss_row_id": i,
            "chunk_id": chunk["chunk_id"],
            "species_key": chunk["species_key"],
        })
        chunk_records.append(chunk)

    pd.DataFrame(index_meta).to_parquet("data/gold/faiss_index/metadata.parquet", index=False)
    pd.DataFrame(chunk_records).to_parquet("data/gold/faiss_index/chunks.parquet", index=False)


def _load_index_and_metadata():
    index = faiss.read_index("data/gold/faiss_index/index.faiss")
    meta = pd.read_parquet("data/gold/faiss_index/metadata.parquet")
    chunks_df = pd.read_parquet("data/gold/faiss_index/chunks.parquet")
    chunks_map = dict(zip(chunks_df["chunk_id"], chunks_df["text"]))
    return index, meta, chunks_map


def _get_merged_for_species(species_key: str) -> dict | None:
    try:
        import duckdb
        conn = duckdb.connect("data/warehouse.duckdb")
        row = conn.execute(
            "SELECT * FROM species_merged WHERE species_key = ?", [species_key]
        ).fetchone()
        if row is None:
            conn.close()
            return None
        columns = [desc[0] for desc in conn.description]
        conn.close()
        return dict(zip(columns, row))
    except Exception:
        return None


def search(
    query: str,
    top_k: int = 5,
    filtro_taxonomia: Optional[dict] = None,
    filtro_iucn: Optional[str] = None,
    filtro_pais: Optional[str] = None,
) -> list[dict]:
    if not query or not os.path.exists("data/gold/faiss_index/index.faiss"):
        return []

    model = _get_model()
    q_emb = model.encode([query], normalize_embeddings=True)
    q_emb = np.array(q_emb, dtype=np.float32)

    index, meta_df, chunks_map = _load_index_and_metadata()
    if index.ntotal == 0:
        return []

    oversample_k = min(top_k * 5, index.ntotal)
    scores, indices = index.search(q_emb, oversample_k)

    results: list[dict] = []
    seen_species: set[str] = set()

    for score, idx in zip(scores[0], indices[0]):
        if idx == -1:
            continue
        row = meta_df.iloc[idx]
        sk = row["species_key"]
        if sk in seen_species:
            continue

        merged = _get_merged_for_species(sk)
        if merged is None:
            continue

        if filtro_taxonomia:
            skip = False
            for k, v in filtro_taxonomia.items():
                if merged.get(k) != v:
                    skip = True
                    break
            if skip:
                continue

        if filtro_iucn:
            if merged.get("iucn_red_list_category") != filtro_iucn:
                continue

        if filtro_pais:
            paises = merged.get("paises", [])
            if filtro_pais not in paises:
                continue

        seen_species.add(sk)
        chunk_id = row["chunk_id"]
        chunk_text = chunks_map.get(chunk_id, "")

        results.append({
            "species_key": sk,
            "wikipedia_title": merged.get("wikipedia_title", ""),
            "chunk_text": chunk_text,
            "score": float(score),
            "metadata": {
                "kingdom": merged.get("kingdom"),
                "phylum": merged.get("phylum"),
                "class_name": merged.get("class_name"),
                "rank": merged.get("rank"),
                "taxonomy_status": merged.get("taxonomy_status"),
                "iucn_red_list_category": merged.get("iucn_red_list_category"),
                "paises": merged.get("paises", []),
                "anio_min": merged.get("anio_min"),
                "anio_max": merged.get("anio_max"),
                "n_occurrences_validas": merged.get("n_occurrences_validas", 0),
                "augmentation_status": merged.get("augmentation_status"),
            },
        })

        if len(results) >= top_k:
            break

    return results
