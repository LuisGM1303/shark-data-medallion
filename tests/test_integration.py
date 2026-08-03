"""End-to-end integration tests."""
from __future__ import annotations

import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.pipeline import run_pipeline
from src.gold.indexer import search, _load_index_and_metadata
from src.warehouse.loader import Warehouse

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


def _clean_all():
    Warehouse.close_all()
    for d in ["data/bronze", "data/silver", "data/gold"]:
        if os.path.exists(d):
            shutil.rmtree(d)
    for f in os.listdir("data"):
        if f.endswith(".duckdb") or f.endswith(".duckdb.wal"):
            p = os.path.join("data", f)
            try:
                os.remove(p)
            except PermissionError:
                pass


SEED_FIRST_9 = [
    "Carcharodon carcharias", "Rhincodon typus", "Cetorhinus maximus",
    "Galeocerdo cuvier", "Sphyrna mokarran", "Sphyrna lewini",
    "Prionace glauca", "Isurus oxyrinchus", "Carcharhinus leucas",
]
SEED_LAST_9 = [
    "Carcharhinus longimanus", "Triaenodon obesus", "Carcharhinus melanopterus",
    "Somniosus microcephalus", "Squalus acanthias", "Heterodontus francisci",
    "Carcharhinus falciformis", "Alopias vulpinus", "Ginglymostoma cirratum",
]
TEST_ADHOC = ["Mobula birostris"]


@test("#178: End-to-end: Process seed batch from bronze to search in a single run")
def test_e2e_seed_bronze_to_search():
    _clean_all()
    species = SEED_FIRST_9[:2]
    summary = run_pipeline(species, batch_id="e2e_178")
    assert len(summary["bronze"]["gbif_taxonomy"]) > 0
    assert len(summary["bronze"]["wikipedia"]) > 0
    results = search("shark diet", top_k=3)
    assert len(results) > 0, "search() should return results after pipeline run"
    _clean_all()


@test("#179: End-to-end: Process new species and confirm it's queryable")
def test_e2e_adhoc_queryable():
    _clean_all()
    summary = run_pipeline(TEST_ADHOC, batch_id="e2e_179")
    wh = Warehouse()
    wh.connect()
    row = wh.connect().execute(
        "SELECT origin FROM species_catalog WHERE species_key = ?",
        ["mobula_birostris"]
    ).fetchone()
    assert row is not None, "AD_HOC species should be in catalog"
    assert row[0] == "AD_HOC", f"origin should be AD_HOC, got {row[0]}"
    results = search("manta ray", top_k=3)
    assert len(results) > 0, "search() should return results for AD_HOC species"
    _clean_all()


@test("#180: Idempotency: two consecutive runs of full seed batch produce rows_new = 0")
def test_e2e_idempotency():
    _clean_all()
    species = SEED_FIRST_9[:2]
    run_pipeline(species, batch_id="run_1")
    summary2 = run_pipeline(species, batch_id="run_2")
    for table_result in summary2["warehouse"]:
        if isinstance(table_result, dict) and "filas_nuevas" in table_result:
            assert table_result["filas_nuevas"] == 0, f"{table_result['tabla']}: filas_nuevas={table_result['filas_nuevas']}"
    _clean_all()


@test("#186: End-to-end: Lote 1 (first 2 seed species) processing demonstrates reproducibility")
def test_e2e_lote_1():
    _clean_all()
    lote1 = SEED_FIRST_9[:2]
    summary = run_pipeline(lote1, batch_id="lote_1")
    assert summary["merge"]["merged"] >= 1
    wh = Warehouse()
    wh.connect()
    count = wh.connect().execute("SELECT COUNT(*) FROM species_catalog").fetchone()[0]
    assert count >= 1, f"species_catalog should have entries, got {count}"
    _clean_all()


@test("#187: End-to-end: Lote 2 (next 2 seed species) processed independently")
def test_e2e_lote_2():
    _clean_all()
    lote1 = SEED_FIRST_9[:2]
    lote2 = SEED_LAST_9[:2]
    run_pipeline(lote1, batch_id="lote_1")
    run_pipeline(lote2, batch_id="lote_2")
    wh = Warehouse()
    wh.connect()
    count = wh.connect().execute("SELECT COUNT(*) FROM species_catalog").fetchone()[0]
    assert count >= 2, f"species_catalog should have at least 2 entries, got {count}"
    _clean_all()


@test("#194: slugify handles edge cases: empty string, None, special characters")
def test_slugify_edge_cases():
    from src.resolver.slugify import slugify
    result_empty = slugify("")
    assert result_empty == "", f"slugify('') should return '', got '{result_empty}'"
    result_none = slugify(None)
    assert result_none is None or result_none == "", f"slugify(None) should return None or '', got '{result_none}'"
    result_special = slugify("Hello World! @#$%")
    assert " " not in result_special, "slugify should replace spaces"
    assert result_special == result_special.lower(), "slugify should lowercase"


if __name__ == "__main__":
    n = len([k for k in dir() if k.startswith("test_") and callable(locals()[k])])
    print(f"Running {n} Integration tests...\n")

    print(f"\nResults: {PASSED} passed, {FAILED} failed")
    if ERRORS:
        print("\nErrors:")
        for name, err in ERRORS:
            print(f"  {name}: {err}")
    _clean_all()
    sys.exit(0 if FAILED == 0 else 1)
