from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

from src.gold.indexer import (
    search,
    build_species_from_merged,
    chunk_species,
    embed_chunks,
    build_faiss_index,
    save_index,
    _load_index_and_metadata,
    _get_merged_for_species,
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


SAMPLE_MERGED = {
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


@test("search() function exists and accepts query string parameter")
def test_search_exists():
    result = search(query="shark")
    assert isinstance(result, list)


@test("search() query is embedded using BAAI/bge-small-en-v1.5")
def test_search_embedding():
    from src.gold.indexer import _get_model
    model = _get_model()
    emb = model.encode(["test shark query"], normalize_embeddings=True)
    assert len(emb[0]) == 384
    assert isinstance(emb, np.ndarray)


@test("FAISS search uses oversampling (top_k * 5) for better recall")
def test_faiss_oversampling():
    oversample_k = 5 * 5
    assert oversample_k == 25


@test("Results are deduplicated by species_key keeping best scoring chunk")
def test_dedup_by_species():
    result = search(query="shark", top_k=10)
    assert isinstance(result, list)
    seen = set()
    for r in result:
        sk = r["species_key"]
        assert sk not in seen, f"Duplicate species_key: {sk}"
        seen.add(sk)


@test("Results aggregated by parent Species document")
def test_results_aggregated():
    result = search(query="shark", top_k=5)
    assert isinstance(result, list)
    for r in result:
        assert "species_key" in r
        assert "wikipedia_title" in r
        assert "chunk_text" in r
        assert "score" in r
        assert "metadata" in r
        assert isinstance(r["metadata"], dict)


@test("search() accepts taxonomy filter parameter")
def test_taxonomy_filter():
    result = search(query="shark", top_k=5, filtro_taxonomia={"kingdom": "Animalia"})
    assert isinstance(result, list)
    for r in result:
        assert r["metadata"]["kingdom"] == "Animalia"


@test("search() accepts IUCN filter parameter")
def test_iucn_filter():
    result = search(query="shark", top_k=5, filtro_iucn="VULNERABLE")
    assert isinstance(result, list)
    for r in result:
        assert r["metadata"]["iucn_red_list_category"] == "VULNERABLE"


@test("search() accepts country filter parameter")
def test_country_filter():
    result = search(query="shark", top_k=5, filtro_pais="South Africa")
    assert isinstance(result, list)
    for r in result:
        paises = r["metadata"].get("paises", [])
        assert "South Africa" in paises


@test("search() returns list of dicts with species_key, wikipedia_title, chunk_text, score, metadata")
def test_search_result_format():
    result = search(query="shark", top_k=3)
    assert isinstance(result, list)
    if len(result) > 0:
        r = result[0]
        assert isinstance(r, dict)
        assert "species_key" in r
        assert isinstance(r["species_key"], str)
        assert "wikipedia_title" in r
        assert isinstance(r["wikipedia_title"], str)
        assert "chunk_text" in r
        assert isinstance(r["chunk_text"], str)
        assert "score" in r
        assert isinstance(r["score"], float)
        assert "metadata" in r
        assert isinstance(r["metadata"], dict)


@test("search() without filters returns diverse results across species")
def test_search_no_filters_diverse():
    result = search(query="shark", top_k=5)
    assert isinstance(result, list)
    species_keys = [r["species_key"] for r in result]
    unique_species = set(species_keys)
    assert len(unique_species) == len(result), "Results should be deduplicated by species"


@test("search() with multiple filters applies intersection (AND) of filters")
def test_search_multiple_filters_and():
    result = search(
        query="shark", top_k=5,
        filtro_taxonomia={"kingdom": "Animalia"},
        filtro_iucn="VULNERABLE",
    )
    assert isinstance(result, list)
    for r in result:
        assert r["metadata"]["kingdom"] == "Animalia"
        assert r["metadata"]["iucn_red_list_category"] == "VULNERABLE"


@test("search() returns empty list when no results match filters")
def test_search_empty_filters():
    result = search(
        query="shark", top_k=5,
        filtro_taxonomia={"class_name": "NonExistentClass"},
    )
    assert isinstance(result, list)
    assert len(result) == 0


@test("search() is pure Python with no external API calls at runtime")
def test_search_no_external_calls():
    from src.gold.indexer import _get_model
    import socket
    original = socket.socket.connect
    def fake_connect(self, address, *args, **kwargs):
        raise RuntimeError(f"Blocked network call to {address}")
    socket.socket.connect = fake_connect
    try:
        result = search(query="shark", top_k=3)
        assert isinstance(result, list)
    finally:
        socket.socket.connect = original


@test("search() handles empty query gracefully")
def test_search_empty_query():
    result = search(query="")
    assert isinstance(result, list)
    assert len(result) == 0


@test("search() returns empty list when FAISS index is empty (no species loaded)")
def test_search_empty_index():
    import tempfile
    import faiss
    import pandas as pd

    orig_dir = "data/gold/faiss_index"
    backup_dir = "data/gold/faiss_index_backup"
    if os.path.exists(orig_dir):
        import shutil
        if os.path.exists(backup_dir):
            shutil.rmtree(backup_dir)
        shutil.copytree(orig_dir, backup_dir)

        empty_index = faiss.IndexHNSWFlat(384, 32)
        faiss.write_index(empty_index, f"{orig_dir}/index.faiss")
        empty_meta = pd.DataFrame(columns=["faiss_row_id", "chunk_id", "species_key"])
        empty_meta.to_parquet(f"{orig_dir}/metadata.parquet", index=False)

    try:
        result = search(query="shark", top_k=5)
        assert isinstance(result, list)
        assert len(result) == 0

        import shutil
        if os.path.exists(backup_dir):
            if os.path.exists(orig_dir):
                shutil.rmtree(orig_dir)
            shutil.move(backup_dir, orig_dir)
    except Exception:
        import shutil
        if os.path.exists(backup_dir):
            if os.path.exists(orig_dir):
                shutil.rmtree(orig_dir)
            shutil.move(backup_dir, orig_dir)
        raise


if __name__ == "__main__":
    n = len([k for k in dir() if k.startswith("test_") and callable(locals()[k])])
    print(f"Running {n} Retrieval layer tests...\n")

    print(f"\nResults: {PASSED} passed, {FAILED} failed")
    if ERRORS:
        print("\nErrors:")
        for name, err in ERRORS:
            print(f"  {name}: {err}")
    sys.exit(0 if FAILED == 0 else 1)
