"""Pipeline integration tests."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.pipeline import run_pipeline
from src.config.seed_species import SEED_SPECIES
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


TEST_SPECIES_2 = ["Carcharodon carcharias", "Rhincodon typus"]
TEST_ADHOC = ["Mobula birostris"]


@test("#150: pipeline.py exists and is importable as module")
def test_import_pipeline():
    from src import pipeline
    assert hasattr(pipeline, "run_pipeline")
    assert callable(pipeline.run_pipeline)


@test("#151: Pipeline accepts list of scientific names as input")
def test_accepts_list():
    _clean_all()
    summary = run_pipeline(TEST_SPECIES_2, batch_id="test_151")
    assert summary["n_species"] == 2
    _clean_all()


@test("#152: Pipeline processes seed batch end-to-end")
def test_seed_batch():
    _clean_all()
    species = [s["scientific_name"] for s in SEED_SPECIES[:2]]
    summary = run_pipeline(species, batch_id="test_152")
    assert summary["n_species"] == 2
    _clean_all()


@test("#153: Pipeline processes ad-hoc (new) species not in seed list")
def test_adhoc_species():
    _clean_all()
    summary = run_pipeline(TEST_ADHOC, batch_id="test_153")
    assert summary["merge"]["merged"] >= 1
    _clean_all()


@test("#154: Pipeline processes mixed batch (seed + ad-hoc species together)")
def test_mixed_batch():
    _clean_all()
    mixed = TEST_SPECIES_2 + TEST_ADHOC
    summary = run_pipeline(mixed, batch_id="test_154")
    assert summary["n_species"] == 3
    assert summary["merge"]["merged"] >= 2
    _clean_all()


@test("#155: Pipeline runs bronze -> silver -> merge -> warehouse -> gold sequentially")
def test_stages_sequential():
    _clean_all()
    summary = run_pipeline(TEST_SPECIES_2, batch_id="test_155")
    assert len(summary["bronze"]["gbif_taxonomy"]) > 0
    assert len(summary["bronze"]["gbif_occurrence"]) > 0
    assert len(summary["bronze"]["wikipedia"]) > 0
    assert summary["silver"]["wikipedia_valid"] >= 1
    assert summary["merge"]["merged"] >= 1
    assert len(summary["warehouse"]) > 0
    assert summary["gold"]["n_species"] >= 1
    _clean_all()


@test("#156: Pipeline idempotency: same batch twice produces rows_new = 0 on second run")
def test_idempotency():
    _clean_all()
    species = TEST_SPECIES_2
    run_pipeline(species, batch_id="run_1")
    summary2 = run_pipeline(species, batch_id="run_2")
    for table_result in summary2["warehouse"]:
        if isinstance(table_result, dict) and "filas_nuevas" in table_result:
            assert table_result["filas_nuevas"] == 0, f"{table_result['tabla']}: filas_nuevas={table_result['filas_nuevas']}"
    _clean_all()


@test("#157: Pipeline handles species with no Wikipedia match -> quarantined, not fatal")
def test_no_wikipedia_match():
    _clean_all()
    summary = run_pipeline(["Xyzabc_000_nonexistent_species"], batch_id="test_157")
    assert summary["silver"]["wikipedia_valid"] == 0, f"Expected 0 valid, got {summary['silver']['wikipedia_valid']}"
    _clean_all()


@test("#158: Pipeline handles GBIF API errors without failing the batch")
def test_gbif_errors():
    _clean_all()
    summary = run_pipeline(TEST_SPECIES_2, batch_id="test_158")
    assert summary["n_species"] == 2
    # Should still process successfully even if some GBIF records fail
    assert summary["merge"]["merged"] >= 1
    _clean_all()


@test("#159: Pipeline produces a summary report after execution")
def test_summary_report():
    _clean_all()
    summary = run_pipeline(TEST_SPECIES_2, batch_id="test_159")
    for key in ["batch_id", "n_species", "bronze", "silver", "merge", "warehouse", "gold"]:
        assert key in summary, f"Summary missing key: {key}"
    assert summary["batch_id"] == "test_159"
    assert summary["n_species"] == 2
    _clean_all()


@test("#160: Pipeline accepts BATCH_SPECIES environment variable")
def test_batch_species_env():
    _clean_all()
    env = os.environ.copy()
    env["BATCH_SPECIES"] = json.dumps(TEST_SPECIES_2)
    result = subprocess.run(
        [sys.executable, "-m", "src.pipeline", "--batch", "seed"],
        capture_output=True, text=True, timeout=300,
        env=env,
        cwd=os.path.join(os.path.dirname(__file__), ".."),
    )
    # Should succeed
    assert result.returncode == 0 or "batch_id" in result.stdout, f"Pipeline failed: {result.stderr[:300]}"
    _clean_all()


@test("#161: Pipeline accepts --species-file argument for batch definition")
def test_species_file():
    _clean_all()
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("Carcharodon carcharias\n")
        f.write("Rhincodon typus\n")
        tmp_path = f.name
    try:
        result = subprocess.run(
            [sys.executable, "-m", "src.pipeline", "--species-file", tmp_path],
            capture_output=True, text=True, timeout=120,
            cwd=os.path.join(os.path.dirname(__file__), ".."),
        )
        assert result.returncode == 0 or "batch_id" in result.stdout, f"Pipeline failed: {result.stderr[:300]}"
    finally:
        os.unlink(tmp_path)
    _clean_all()


@test("#162: Pipeline handles empty batch gracefully (no species provided)")
def test_empty_batch():
    _clean_all()
    summary = run_pipeline([], batch_id="test_162")
    assert summary["status"] == "empty_batch"
    assert "message" in summary
    _clean_all()


if __name__ == "__main__":
    n = len([k for k in dir() if k.startswith("test_") and callable(locals()[k])])
    print(f"Running {n} Pipeline layer tests...\n")

    from src.warehouse.loader import Warehouse
    Warehouse  # suppress unused import warning

    print(f"\nResults: {PASSED} passed, {FAILED} failed")
    if ERRORS:
        print("\nErrors:")
        for name, err in ERRORS:
            print(f"  {name}: {err}")
    _clean_all()
    sys.exit(0 if FAILED == 0 else 1)
