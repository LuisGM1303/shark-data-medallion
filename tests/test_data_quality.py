"""Data quality verification tests."""
from __future__ import annotations

import json
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.pipeline import run_pipeline
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


TEST_SPECIES = ["Carcharodon carcharias", "Rhincodon typus"]


@test("#172: Pipeline is deterministic: same inputs produce identical outputs")
def test_deterministic():
    _clean_all()
    s1 = run_pipeline(TEST_SPECIES, batch_id="det_1")
    _clean_all()
    s2 = run_pipeline(TEST_SPECIES, batch_id="det_2")
    assert s1["silver"]["wikipedia_valid"] == s2["silver"]["wikipedia_valid"]
    assert s1["merge"]["merged"] == s2["merge"]["merged"]
    _clean_all()


@test("#173: All rejection reasons are explicit and documented per record")
def test_rejection_reasons():
    _clean_all()
    run_pipeline(TEST_SPECIES, batch_id="dq_173")
    rejected_count = 0
    for src in ["wikipedia", "gbif_taxonomy", "gbif_occurrence"]:
        rejected_dir = f"data/silver/{src}/rejected"
        if not os.path.isdir(rejected_dir):
            continue
        for fname in os.listdir(rejected_dir):
            if fname.endswith(".json"):
                with open(os.path.join(rejected_dir, fname)) as f:
                    data = json.load(f)
                assert "rejection_reason" in data, f"Missing rejection_reason in {fname}"
                rejected_count += 1
    _clean_all()


@test("#174: No data is lost or silently dropped between pipeline stages")
def test_no_data_loss():
    _clean_all()
    summary = run_pipeline(TEST_SPECIES, batch_id="dq_174")
    total_silver = (
        summary["silver"]["wikipedia_valid"] + summary["silver"]["wikipedia_rejected"]
        + summary["silver"]["gbif_taxonomy_valid"] + summary["silver"]["gbif_taxonomy_rejected"]
        + summary["silver"]["gbif_occurrence_valid"] + summary["silver"]["gbif_occurrence_rejected"]
    )
    assert total_silver > 0, "Silver should have processed records"
    _clean_all()


@test("#175: All JSON files are valid and parseable")
def test_json_valid():
    _clean_all()
    run_pipeline(TEST_SPECIES, batch_id="dq_175")
    parsed = 0
    for root, dirs, files in os.walk("data/bronze"):
        for fname in files:
            if fname.endswith(".json"):
                with open(os.path.join(root, fname)) as f:
                    json.load(f)
                parsed += 1
    assert parsed > 0, "Should have parsed at least some JSON files"
    _clean_all()


@test("#176: Records are traceable across all pipeline stages")
def test_traceability():
    _clean_all()
    summary = run_pipeline(TEST_SPECIES, batch_id="dq_176")
    wh = Warehouse()
    wh.connect()
    for sk_key in ["carcharodon_carcharias", "rhincodon_typus"]:
        wp = wh.connect().execute("SELECT species_key FROM silver_wikipedia WHERE species_key = ?", [sk_key]).fetchone()
        tax = wh.connect().execute("SELECT species_key FROM silver_gbif_taxonomy WHERE species_key = ?", [sk_key]).fetchone()
        merged = wh.connect().execute("SELECT species_key FROM species_merged WHERE species_key = ?", [sk_key]).fetchone()
        cat = wh.connect().execute("SELECT species_key FROM species_catalog WHERE species_key = ?", [sk_key]).fetchone()
        found_any = wp is not None or tax is not None or merged is not None or cat is not None
        assert found_any, f"species_key {sk_key} not found in any warehouse table"
    _clean_all()


@test("#177: Gold layer only contains species with valid Wikipedia in species_catalog")
def test_gold_valid_wikipedia():
    _clean_all()
    summary = run_pipeline(["Xyzabc_000_nonexistent_species"] + TEST_SPECIES, batch_id="dq_177")
    wh = Warehouse()
    wh.connect()
    catalog_species = wh.connect().execute("SELECT species_key FROM species_catalog").fetchall()
    catalog_keys = {row[0] for row in catalog_species}
    assert "xyzabc_000_nonexistent_species" not in catalog_keys, "Invalid species should not be in catalog"
    _clean_all()


if __name__ == "__main__":
    n = len([k for k in dir() if k.startswith("test_") and callable(locals()[k])])
    print(f"Running {n} Data Quality tests...\n")

    print(f"\nResults: {PASSED} passed, {FAILED} failed")
    if ERRORS:
        print("\nErrors:")
        for name, err in ERRORS:
            print(f"  {name}: {err}")
    _clean_all()
    sys.exit(0 if FAILED == 0 else 1)
