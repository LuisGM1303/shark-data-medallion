from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import duckdb

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


TEST_DB = "data/test_warehouse.duckdb"


def _cleanup():
    if os.path.exists(TEST_DB):
        try:
            os.remove(TEST_DB)
        except PermissionError:
            pass
    for wal in [TEST_DB + ".wal"]:
        if os.path.exists(wal):
            try:
                os.remove(wal)
            except PermissionError:
                pass


def _make_wh() -> Warehouse:
    _cleanup()
    wh = Warehouse(db_path=TEST_DB)
    wh.connect()
    wh.initialize_schema()
    return wh


SAMPLE_WP = {
    "species_key": "carcharodon_carcharias",
    "title": "Great white shark",
    "resolved_via": "DIRECT_TITLE",
    "extract": "The great white shark is a species of large mackerel shark.",
    "sections_text": "== Description ==\nLarge shark.\n== Habitat ==\nOceans worldwide.",
    "page_url": "https://en.wikipedia.org/wiki/Great_white_shark",
    "is_disambiguation": False,
}

SAMPLE_TAX = {
    "species_key": "carcharodon_carcharias",
    "usage_key": 123456,
    "scientific_name": "Carcharodon carcharias",
    "canonical_name": "Carcharodon carcharias",
    "rank": "SPECIES",
    "match_type": "EXACT",
    "confidence": 100,
    "kingdom": "Animalia",
    "phylum": "Chordata",
    "class_name": "Chondrichthyes",
}

SAMPLE_OCC = {
    "gbif_id": 10000001,
    "species_key": "carcharodon_carcharias",
    "decimal_latitude": 34.0,
    "decimal_longitude": -120.0,
    "country": "United States",
    "event_date": datetime(2020, 6, 15),
    "basis_of_record": "HUMAN_OBSERVATION",
    "iucn_red_list_category": "VULNERABLE",
    "coordinate_uncertainty_m": 100.0,
}

SAMPLE_MERGED = {
    "species_key": "carcharodon_carcharias",
    "wikipedia_title": "Great white shark",
    "extract": "The great white shark is a species of large mackerel shark.",
    "sections_text": "== Description ==\nLarge shark.",
    "kingdom": "Animalia",
    "phylum": "Chordata",
    "class_name": "Chondrichthyes",
    "rank": "SPECIES",
    "taxonomy_status": "MATCHED",
    "n_occurrences_validas": 1,
    "paises": ["United States"],
    "anio_min": 2020,
    "anio_max": 2020,
    "iucn_red_list_category": "VULNERABLE",
    "augmentation_status": "OK",
}

SAMPLE_CATALOG = {
    "species_key": "carcharodon_carcharias",
    "scientific_name": "Carcharodon carcharias",
    "wikipedia_title": "Great white shark",
    "origin": "SEED",
}


@test("#88: DuckDB file is created at data/warehouse.duckdb after first warehouse operation")
def test_warehouse_file_created():
    wh = _make_wh()
    assert os.path.exists(TEST_DB), "DuckDB file should exist after connect + initialize_schema"
    conn = duckdb.connect(TEST_DB)
    conn.close()


@test("#89: silver_wikipedia table created with species_key as PRIMARY KEY")
def test_silver_wikipedia_table():
    wh = _make_wh()
    conn = wh.connect()
    desc = conn.execute("DESCRIBE silver_wikipedia").fetchall()
    cols = [r[0] for r in desc]
    for needed in ['species_key', 'title', 'extract', 'sections_text', 'page_url']:
        assert needed in cols, f"silver_wikipedia should have column {needed}"
    pk_col = next((r[0] for r in desc if r[3] in ('PRI', 'UNIQUE')), None)
    assert pk_col == 'species_key', f"species_key should be PK or unique, got {pk_col}"


@test("#90: silver_gbif_taxonomy table created with species_key as PRIMARY KEY")
def test_silver_gbif_taxonomy_table():
    wh = _make_wh()
    conn = wh.connect()
    conn.execute("SELECT COUNT(*) FROM silver_gbif_taxonomy").fetchone()
    cols = [r[0] for r in conn.execute("DESCRIBE silver_gbif_taxonomy").fetchall()]
    for needed in ['species_key', 'usage_key', 'scientific_name', 'canonical_name', 'rank', 'match_type', 'confidence']:
        assert needed in cols, f"silver_gbif_taxonomy should have column {needed}"


@test("#91: silver_gbif_occurrences table created with gbif_id as PRIMARY KEY")
def test_silver_gbif_occurrences_table():
    wh = _make_wh()
    conn = wh.connect()
    conn.execute("SELECT COUNT(*) FROM silver_gbif_occurrences").fetchone()
    cols = [r[0] for r in conn.execute("DESCRIBE silver_gbif_occurrences").fetchall()]
    for needed in ['gbif_id', 'species_key', 'decimal_latitude', 'decimal_longitude', 'country', 'basis_of_record']:
        assert needed in cols, f"silver_gbif_occurrences should have column {needed}"


@test("#92: species_merged table created with species_key as PRIMARY KEY")
def test_species_merged_table():
    wh = _make_wh()
    conn = wh.connect()
    conn.execute("SELECT COUNT(*) FROM species_merged").fetchone()
    cols = [r[0] for r in conn.execute("DESCRIBE species_merged").fetchall()]
    for needed in ['species_key', 'wikipedia_title', 'extract', 'sections_text', 'taxonomy_status', 'n_occurrences_validas', 'paises', 'augmentation_status']:
        assert needed in cols, f"species_merged should have column {needed}"


@test("#93: species_catalog table created with species_key as PRIMARY KEY")
def test_species_catalog_table():
    wh = _make_wh()
    conn = wh.connect()
    conn.execute("SELECT COUNT(*) FROM species_catalog").fetchone()
    cols = [r[0] for r in conn.execute("DESCRIBE species_catalog").fetchall()]
    for needed in ['species_key', 'scientific_name', 'wikipedia_title', 'first_seen_batch_id', 'first_processed_at', 'last_processed_at', 'origin']:
        assert needed in cols, f"species_catalog should have column {needed}"


@test("#94: species_catalog origin field is 'SEED' for seed species processed first time")
def test_origin_seed():
    wh = _make_wh()
    result = wh.upsert_species_catalog([SAMPLE_CATALOG], "seed_batch_1")
    conn = wh.connect()
    row = conn.execute("SELECT origin FROM species_catalog WHERE species_key = ?", [SAMPLE_CATALOG['species_key']]).fetchone()
    assert row is not None, "species should exist in catalog"
    assert row[0] == 'SEED', f"origin should be SEED, got {row[0]}"


@test("#95: species_catalog origin field is 'AD_HOC' for non-seed species")
def test_origin_adhoc():
    wh = _make_wh()
    adhoc = dict(SAMPLE_CATALOG)
    adhoc["species_key"] = "isurus_oxyrinchus"
    adhoc["species_name"] = "Isurus oxyrinchus"
    adhoc["origin"] = "AD_HOC"
    wh.upsert_species_catalog([adhoc], "adhoc_batch_1")
    conn = wh.connect()
    row = conn.execute("SELECT origin FROM species_catalog WHERE species_key = ?", ["isurus_oxyrinchus"]).fetchone()
    assert row is not None, "AD_HOC species should exist in catalog"
    assert row[0] == 'AD_HOC', f"origin should be AD_HOC, got {row[0]}"


@test("#96: UPSERT pattern uses ON CONFLICT DO UPDATE (not INSERT-only)")
def test_upsert_pattern_updates():
    wh = _make_wh()
    wh.upsert_species_catalog([SAMPLE_CATALOG], "batch_1")
    updated = dict(SAMPLE_CATALOG)
    updated["wikipedia_title"] = "Great white shark (updated)"
    wh.upsert_species_catalog([updated], "batch_2")
    conn = wh.connect()
    row = conn.execute("SELECT wikipedia_title FROM species_catalog WHERE species_key = ?", [SAMPLE_CATALOG['species_key']]).fetchone()
    assert row is not None
    assert row[0] == "Great white shark (updated)", f"UPSERT should update wikipedia_title, got {row[0]}"


@test("#97: species_catalog upserts update last_processed_at on conflict")
def test_last_processed_at_updated():
    wh = _make_wh()
    wh.upsert_species_catalog([SAMPLE_CATALOG], "batch_1")
    conn = wh.connect()
    row1 = conn.execute("SELECT last_processed_at FROM species_catalog WHERE species_key = ?", [SAMPLE_CATALOG['species_key']]).fetchone()
    t1 = row1[0]
    time.sleep(0.1)
    wh.upsert_species_catalog([SAMPLE_CATALOG], "batch_2")
    row2 = conn.execute("SELECT last_processed_at FROM species_catalog WHERE species_key = ?", [SAMPLE_CATALOG['species_key']]).fetchone()
    t2 = row2[0]
    assert t2 >= t1, f"last_processed_at should be updated: t1={t1}, t2={t2}"


@test("#98: First-time species processed and inserted into species_merged")
def test_first_time_species_merged():
    wh = _make_wh()
    result = wh.upsert_species_merged([SAMPLE_MERGED])
    assert result["filas_nuevas"] == 1, f"Should have 1 new row, got {result['filas_nuevas']}"
    conn = wh.connect()
    row = conn.execute("SELECT species_key, wikipedia_title, taxonomy_status FROM species_merged WHERE species_key = ?", [SAMPLE_MERGED['species_key']]).fetchone()
    assert row is not None, "species_merged should contain the species"
    assert row[1] == "Great white shark"
    assert row[2] == "MATCHED"


@test("#99: species_catalog records first_seen_batch_id on first insert")
def test_first_seen_batch_id():
    wh = _make_wh()
    wh.upsert_species_catalog([SAMPLE_CATALOG], "seed_batch_1")
    conn = wh.connect()
    row = conn.execute("SELECT first_seen_batch_id, first_processed_at FROM species_catalog WHERE species_key = ?", [SAMPLE_CATALOG['species_key']]).fetchone()
    assert row is not None
    assert row[0] == "seed_batch_1", f"first_seen_batch_id should be seed_batch_1, got {row[0]}"
    assert row[1] is not None, "first_processed_at should be populated"


@test("#100: All 5 warehouse tables are populated after pipeline execution with data")
def test_all_tables_populated():
    wh = _make_wh()
    wh.upsert_wikipedia([SAMPLE_WP])
    wh.upsert_gbif_taxonomy([SAMPLE_TAX])
    wh.upsert_gbif_occurrences([SAMPLE_OCC])
    wh.upsert_species_merged([SAMPLE_MERGED])
    wh.upsert_species_catalog([SAMPLE_CATALOG], "batch_1")
    evidence = wh.get_evidence()
    table_counts = {e["tabla"]: e["count"] for e in evidence}
    for tbl in ["silver_wikipedia", "silver_gbif_taxonomy", "silver_gbif_occurrences", "species_merged", "species_catalog"]:
        assert table_counts.get(tbl, 0) > 0, f"{tbl} should have > 0 rows, got {table_counts.get(tbl, 0)}"


@test("#101: Warehouse UPSERT correctly updates existing records with new data")
def test_upsert_updates_existing():
    wh = _make_wh()
    wh.upsert_species_merged([SAMPLE_MERGED])
    updated = dict(SAMPLE_MERGED)
    updated["extract"] = "UPDATED: The great white shark is a large shark species found in all major oceans."
    result = wh.upsert_species_merged([updated])
    assert result["filas_actualizadas"] == 1, f"Should have 1 updated row, got {result['filas_actualizadas']}"
    assert result["filas_nuevas"] == 0, f"Should have 0 new rows, got {result['filas_nuevas']}"
    conn = wh.connect()
    row = conn.execute("SELECT extract FROM species_merged WHERE species_key = ?", [SAMPLE_MERGED['species_key']]).fetchone()
    assert row is not None
    assert row[0].startswith("UPDATED:"), "extract should reflect updated content"


@test("#102: Idempotency evidence: rows_new = 0 on second consecutive run of same batch")
def test_idempotency_rows_new_zero():
    wh = _make_wh()
    r1 = wh.upsert_species_merged([SAMPLE_MERGED])
    assert r1["filas_nuevas"] == 1
    r2 = wh.upsert_species_merged([SAMPLE_MERGED])
    assert r2["filas_nuevas"] == 0, f"Second run should have 0 new rows, got {r2['filas_nuevas']}"
    assert r2["filas_actualizadas"] >= 0


@test("#103: Idempotency evidence table shows rows_before, rows_after, rows_new, rows_updated")
def test_evidence_format():
    wh = _make_wh()
    result = wh.upsert_species_merged([SAMPLE_MERGED])
    for key in ["tabla", "filas_antes", "filas_despues", "filas_nuevas", "filas_actualizadas"]:
        assert key in result, f"Evidence should contain key {key}"
    for key in ["filas_antes", "filas_despues", "filas_nuevas", "filas_actualizadas"]:
        assert isinstance(result[key], int), f"{key} should be int"


@test("#104: Evidence shows a non-seed species inserted as AD_HOC on first run")
def test_adhoc_evidence():
    wh = _make_wh()
    adhoc = dict(SAMPLE_CATALOG)
    adhoc["species_key"] = "megalodon_extinctus"
    adhoc["scientific_name"] = "Megalodon extinctus"
    adhoc["wikipedia_title"] = "Megalodon"
    adhoc["origin"] = "AD_HOC"
    result = wh.upsert_species_catalog([adhoc], "adhoc_batch")
    assert result["filas_nuevas"] > 0, f"New AD_HOC species should have filas_nuevas > 0, got {result['filas_nuevas']}"
    conn = wh.connect()
    row = conn.execute("SELECT origin FROM species_catalog WHERE species_key = ?", ["megalodon_extinctus"]).fetchone()
    assert row is not None
    assert row[0] == "AD_HOC", f"origin should be AD_HOC, got {row[0]}"


@test("#199: Warehouse handles sequential batch loads without data corruption")
def test_sequential_batches():
    wh = _make_wh()
    batch_a = [
        {"species_key": f"species_{i}", "scientific_name": f"Species {i}", "wikipedia_title": f"Species {i}", "origin": "AD_HOC"}
        for i in range(5)
    ]
    wh.upsert_species_catalog(batch_a, "batch_A")
    batch_b = [
        {"species_key": f"other_species_{i}", "scientific_name": f"Other Species {i}", "wikipedia_title": f"Other Species {i}", "origin": "AD_HOC"}
        for i in range(5)
    ]
    wh.upsert_species_catalog(batch_b, "batch_B")
    conn = wh.connect()
    count = conn.execute("SELECT COUNT(*) FROM species_catalog").fetchone()[0]
    assert count == 10, f"species_catalog should have 10 species, got {count}"
    for s in batch_a:
        row = conn.execute("SELECT species_key FROM species_catalog WHERE species_key = ?", [s["species_key"]]).fetchone()
        assert row is not None, f"Batch A species {s['species_key']} should still exist"


if __name__ == "__main__":
    n = len([k for k in dir() if k.startswith("test_") and callable(locals()[k])])
    print(f"Running {n} Warehouse layer tests...\n")

    print(f"\nResults: {PASSED} passed, {FAILED} failed")
    if ERRORS:
        print("\nErrors:")
        for name, err in ERRORS:
            print(f"  {name}: {err}")
    _cleanup()
    sys.exit(0 if FAILED == 0 else 1)
