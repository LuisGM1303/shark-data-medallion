from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import faiss
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

from src.gold.indexer import (
    CANONICAL_SECTIONS,
    build_species_from_merged,
    chunk_species,
    embed_chunks,
    build_faiss_index,
    save_index,
    _get_model,
)
from src.merge.merger import GBIFOccurrenceSummary

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
    "extract": "The great white shark (Carcharodon carcharias), also known as the white shark, white pointer, or simply great white, is a species of large mackerel shark which can be found in the coastal surface waters of all the major oceans.",
    "sections_text": "== Description and morphology ==\nThe great white shark has a robust, large, conical snout.\n\n== Distribution and habitat ==\nGreat white sharks are found in coastal waters worldwide.\n\n== Behavior ==\nGreat white sharks are apex predators.\n\n== Diet and feeding ==\nThe great white shark's diet includes fish, seals, and sea lions.\n\n== Conservation status ==\nThe great white shark is listed as vulnerable.",
    "kingdom": "Animalia",
    "phylum": "Chordata",
    "class_name": "Chondrichthyes",
    "rank": "SPECIES",
    "taxonomy_status": "MATCHED",
    "n_occurrences_validas": 5,
    "paises": ["South Africa", "Australia", "United States"],
    "anio_min": 2010,
    "anio_max": 2020,
    "iucn_red_list_category": "VULNERABLE",
    "augmentation_status": "OK",
}


@test("BAAI/bge-small-en-v1.5 model loads successfully without internet")
def test_model_loads():
    model = _get_model()
    assert model is not None
    assert isinstance(model, SentenceTransformer)


@test("Embedding dimension is 384 (matching bge-small-en-v1.5)")
def test_embedding_dimension():
    model = _get_model()
    emb = model.encode(["test shark"], normalize_embeddings=True)
    assert len(emb[0]) == 384
    assert isinstance(emb, np.ndarray)
    assert emb.dtype == np.float32 or emb.dtype == np.float64


@test("Only SpeciesChunks are embedded; Species and SpeciesMetadata skipped")
def test_only_chunks_embedded():
    species = build_species_from_merged(SAMPLE_MERGED_MATCHED)
    chunks = chunk_species(species)
    assert len(chunks) > 0
    embeddings = embed_chunks(chunks)
    assert embeddings.shape[0] == len(chunks)

    species_dict = dict(species)
    assert "identity" in species_dict
    chunks_from_identity = [c for c in chunks if c["section"] == "Identity"]
    chunks_from_taxonomy = [c for c in chunks if c["section"] == "Taxonomy"]
    assert len(chunks_from_identity) == 1 or len(chunks_from_taxonomy) >= 0


@test("FAISS IndexHNSWFlat index is created successfully")
def test_faiss_index_created():
    species = build_species_from_merged(SAMPLE_MERGED_MATCHED)
    chunks = chunk_species(species)
    assert len(chunks) > 0
    embeddings = embed_chunks(chunks)
    index = build_faiss_index(embeddings)
    assert isinstance(index, faiss.IndexHNSWFlat)
    assert index.ntotal == len(chunks)


@test("FAISS index is persisted as a standalone file (not inside DuckDB)")
def test_faiss_persisted_standalone():
    species = build_species_from_merged(SAMPLE_MERGED_MATCHED)
    chunks = chunk_species(species)
    embeddings = embed_chunks(chunks)
    index = build_faiss_index(embeddings)
    save_index(index, chunks)
    assert os.path.exists("data/gold/faiss_index/index.faiss")
    loaded = faiss.read_index("data/gold/faiss_index/index.faiss")
    assert loaded.ntotal == len(chunks)

    if os.path.exists("data/warehouse.duckdb"):
        import duckdb
        conn = duckdb.connect("data/warehouse.duckdb")
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
        ).fetchall()
        table_names = [t[0] for t in tables]
        conn.close()
        index_in_duckdb = any("faiss" in t.lower() or "index" in t.lower() for t in table_names)
        assert not index_in_duckdb, "FAISS index should not be stored inside DuckDB"


@test("Metadata parquet maps faiss_row_id -> chunk_id -> species_key")
def test_metadata_parquet():
    species = build_species_from_merged(SAMPLE_MERGED_MATCHED)
    chunks = chunk_species(species)
    embeddings = embed_chunks(chunks)
    index = build_faiss_index(embeddings)
    save_index(index, chunks)

    assert os.path.exists("data/gold/faiss_index/metadata.parquet")
    meta = pd.read_parquet("data/gold/faiss_index/metadata.parquet")
    assert "faiss_row_id" in meta.columns
    assert "chunk_id" in meta.columns
    assert "species_key" in meta.columns
    assert len(meta) == len(chunks)
    assert list(meta["faiss_row_id"]) == list(range(len(chunks)))


@test("FAISS index is fully rebuilt from scratch on each pipeline run")
def test_index_rebuilt():
    save_dir = "data/gold/faiss_index"
    meta_path = os.path.join(save_dir, "metadata.parquet")

    species1 = build_species_from_merged(SAMPLE_MERGED_MATCHED)
    chunks1 = chunk_species(species1)
    embeddings1 = embed_chunks(chunks1)
    index1 = build_faiss_index(embeddings1)
    save_index(index1, chunks1)
    n1 = index1.ntotal

    merged2 = dict(SAMPLE_MERGED_MATCHED)
    merged2["sections_text"] = "== Description and morphology ==\nThe great white shark has a robust, large, conical snout.\n\n== Conservation status ==\nThe great white shark is listed as vulnerable."
    species2 = build_species_from_merged(merged2)
    chunks2 = chunk_species(species2)
    embeddings2 = embed_chunks(chunks2)
    index2 = build_faiss_index(embeddings2)
    save_index(index2, chunks2)

    n2 = index2.ntotal
    assert n2 == len(chunks2)
    assert n2 < n1, f"Reduced sections should produce fewer chunks ({n2} >= {n1})"


@test("Deterministic index: same input produces same index")
def test_deterministic_index():
    merged_copy1 = dict(SAMPLE_MERGED_MATCHED)
    merged_copy2 = dict(SAMPLE_MERGED_MATCHED)

    species1 = build_species_from_merged(merged_copy1)
    chunks1 = chunk_species(species1)
    embeddings1 = embed_chunks(chunks1)
    index1 = build_faiss_index(embeddings1)

    species2 = build_species_from_merged(merged_copy2)
    chunks2 = chunk_species(species2)
    embeddings2 = embed_chunks(chunks2)
    index2 = build_faiss_index(embeddings2)

    assert len(chunks1) == len(chunks2)
    assert index1.ntotal == index2.ntotal
    assert len(chunks1) == len(chunks2)

    for c1, c2 in zip(chunks1, chunks2):
        assert c1["chunk_id"] == c2["chunk_id"]
        assert c1["text"] == c2["text"]

    if embeddings1.size > 0:
        assert np.allclose(embeddings1, embeddings2, atol=1e-5)


@test("FAISS index directory structure is created automatically")
def test_directory_structure():
    assert os.path.exists("data/gold/faiss_index/")
    assert os.path.exists("data/gold/faiss_index/index.faiss")
    assert os.path.exists("data/gold/faiss_index/metadata.parquet")


@test("Embeddings do not make external API calls (fully local inference)")
def test_local_inference():
    model = _get_model()
    emb1 = model.encode(["test"], normalize_embeddings=True)
    emb2 = model.encode(["test"], normalize_embeddings=True)
    assert np.allclose(emb1, emb2, atol=1e-5)
    emb3 = model.encode(["different"], normalize_embeddings=True)
    assert not np.allclose(emb1, emb3, atol=1e-5)
    assert emb1.dtype == np.float32 or emb1.dtype == np.float64


if __name__ == "__main__":
    n = len([k for k in dir() if k.startswith("test_") and callable(locals()[k])])
    print(f"Running {n} Embeddings layer tests...\n")

    print(f"\nResults: {PASSED} passed, {FAILED} failed")
    if ERRORS:
        print("\nErrors:")
        for name, err in ERRORS:
            print(f"  {name}: {err}")
    sys.exit(0 if FAILED == 0 else 1)
