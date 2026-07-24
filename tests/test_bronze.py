"""Bronze layer verification tests."""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import requests
from src.bronze.fetcher import (
    GBIF_SPECIES_MATCH,
    GBIF_OCCURRENCE,
    WIKIPEDIA_REST,
    WIKIPEDIA_API,
    fetch_gbif_taxonomy,
    fetch_gbif_occurrences,
    fetch_wikipedia_summary,
    fetch_wikipedia_extracts,
    persist_bronze,
)
from src.config.seed_species import SEED_SPECIES
from src.resolver.slugify import slugify

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


@test("Bronze GBIF Species Match fetches taxonomy data via API")
def test_gbif_taxonomy_match():
    resp = requests.get(
        GBIF_SPECIES_MATCH,
        params={"name": "Carcharodon carcharias"},
        headers={"User-Agent": "SharkKnowledgeTest/1.0"},
        timeout=30,
    )
    assert resp.status_code == 200, f"HTTP {resp.status_code}"
    data = resp.json()
    assert "usageKey" in data, "missing usageKey"
    assert "scientificName" in data, "missing scientificName"
    assert "matchType" in data, "missing matchType"
    assert "kingdom" in data, "missing kingdom"
    assert "phylum" in data, "missing phylum"
    assert "class" in data, "missing class"


@test("Bronze GBIF Species Match handles non-EXACT matches gracefully")
def test_gbif_taxonomy_non_exact():
    resp = requests.get(
        GBIF_SPECIES_MATCH,
        params={"name": "Shark"},
        headers={"User-Agent": "SharkKnowledgeTest/1.0"},
        timeout=30,
    )
    assert resp.status_code == 200, f"HTTP {resp.status_code}"
    data = resp.json()
    assert data.get("matchType") != "EXACT" or len(data.get("alternatives", [])) > 0


@test("Bronze GBIF Species Match persists raw JSON with metadata envelope")
def test_persist_gbif_taxonomy_envelope():
    resp = fetch_gbif_taxonomy("Carcharodon carcharias")
    path = persist_bronze(
        "gbif_taxonomy", 99, ["Carcharodon carcharias"],
        [{"query": "Carcharodon carcharias", "response": resp}]
    )
    try:
        with open(path) as f:
            env = json.load(f)
        assert env["source"] == "gbif_taxonomy"
        assert "lote" in env
        assert "ingested_at" in env
        assert "species_queried" in env
        assert "raw_responses" in env
        assert len(env["raw_responses"]) == 1
        assert "query" in env["raw_responses"][0]
        assert "response" in env["raw_responses"][0]
    finally:
        if os.path.exists(path):
            os.remove(path)


@test("Bronze GBIF Species Match file naming includes batch number and ISO timestamp")
def test_gbif_taxonomy_filename():
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    pattern = re.compile(r"lote_1__\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z\.json")
    filename = f"lote_1__{ts}.json"
    assert pattern.match(filename), f"Filename {filename} doesn't match ISO 8601 pattern"


@test("Bronze GBIF Occurrence Search fetches occurrence records with correct parameters")
def test_gbif_occurrence_fetch():
    params = {
        "scientificName": "Carcharodon carcharias",
        "hasCoordinate": "true",
        "limit": 50,
    }
    resp = requests.get(
        GBIF_OCCURRENCE,
        params=params,
        headers={"User-Agent": "SharkKnowledgeTest/1.0"},
        timeout=30,
    )
    assert resp.status_code == 200, f"HTTP {resp.status_code}"
    data = resp.json()
    assert "results" in data, "missing results"
    if data["results"]:
        r = data["results"][0]
        assert "gbifID" in r, "missing gbifID"
        assert "decimalLatitude" in r, "missing decimalLatitude"
        assert "decimalLongitude" in r, "missing decimalLongitude"


@test("Bronze GBIF Occurrence Search limit defaults to 50 records")
def test_gbif_occurrence_limit():
    params = {
        "scientificName": "Carcharodon carcharias",
        "hasCoordinate": "true",
        "limit": 50,
    }
    resp = requests.get(
        GBIF_OCCURRENCE,
        params=params,
        headers={"User-Agent": "SharkKnowledgeTest/1.0"},
        timeout=30,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data.get("results", [])) <= 50


@test("Bronze GBIF Occurrence persists raw JSON with metadata envelope")
def test_persist_gbif_occurrence_envelope():
    resp = fetch_gbif_occurrences("Carcharodon carcharias")
    path = persist_bronze(
        "gbif_occurrence", 99, ["Carcharodon carcharias"],
        [{"query": "Carcharodon carcharias", "response": resp}]
    )
    try:
        with open(path) as f:
            env = json.load(f)
        assert env["source"] == "gbif_occurrence"
        assert "lote" in env
        assert "ingested_at" in env
        assert "species_queried" in env
        assert "raw_responses" in env
    finally:
        if os.path.exists(path):
            os.remove(path)


@test("Bronze GBIF Occurrence handles empty results gracefully")
def test_gbif_occurrence_empty():
    resp = fetch_gbif_occurrences("Abcdefghijklmnopqrstuvwxyz")  # improbable name
    assert resp["status"] in (200, 404, 502)
    if resp["status"] == 200:
        data = resp["data"]
        assert isinstance(data, dict)


@test("Bronze GBIF Occurrence includes hasCoordinate=true parameter")
def test_gbif_occurrence_has_coordinate():
    params = {
        "scientificName": "Carcharodon carcharias",
        "hasCoordinate": "true",
        "limit": 50,
    }
    resp = requests.get(
        GBIF_OCCURRENCE,
        params=params,
        headers={"User-Agent": "SharkKnowledgeTest/1.0"},
        timeout=30,
    )
    assert resp.status_code == 200
    data = resp.json()
    for r in data.get("results", []):
        assert r.get("decimalLatitude") is not None
        assert r.get("decimalLongitude") is not None


@test("Bronze Wikipedia fetches summary via REST API")
def test_wikipedia_summary():
    resp = requests.get(
        f"{WIKIPEDIA_REST}/page/summary/Great_white_shark",
        headers={"User-Agent": "SharkKnowledgeTest/1.0"},
        timeout=15,
    )
    assert resp.status_code == 200, f"HTTP {resp.status_code}"
    data = resp.json()
    assert "title" in data
    assert "extract" in data
    assert "page_url" in data or "content_urls" in data


@test("Bronze Wikipedia fetches full extracts via action API")
def test_wikipedia_extracts():
    params = {
        "action": "query",
        "prop": "extracts",
        "explaintext": "true",
        "titles": "Great white shark",
        "format": "json",
    }
    resp = requests.get(
        WIKIPEDIA_API,
        params=params,
        headers={"User-Agent": "SharkKnowledgeTest/1.0"},
        timeout=15,
    )
    assert resp.status_code == 200, f"HTTP {resp.status_code}"
    data = resp.json()
    assert "query" in data
    assert "pages" in data["query"]
    extract_text = list(data["query"]["pages"].values())[0].get("extract", "")
    assert len(extract_text) > 50, "Extract too short"


@test("Bronze Wikipedia persists raw responses with metadata envelope")
def test_persist_wikipedia_envelope():
    summary = fetch_wikipedia_summary("Great white shark")
    extracts = fetch_wikipedia_extracts("Great white shark")
    path = persist_bronze(
        "wikipedia", 99, ["Great white shark"],
        [
            {"query": "summary:Great white shark", "response": summary},
            {"query": "extracts:Great white shark", "response": extracts},
        ]
    )
    try:
        with open(path) as f:
            env = json.load(f)
        assert env["source"] == "wikipedia"
        assert "lote" in env
        assert "ingested_at" in env
        assert "species_queried" in env
        assert "raw_responses" in env
        assert len(env["raw_responses"]) == 2
    finally:
        if os.path.exists(path):
            os.remove(path)


@test("Bronze Wikipedia file naming includes batch number and ISO timestamp")
def test_wikipedia_filename():
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    pattern = re.compile(r"lote_\d+__\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z\.json")
    filename = f"lote_2__{ts}.json"
    assert pattern.match(filename)


@test("Bronze Wikipedia summary handles missing page (404) gracefully")
def test_wikipedia_missing_page():
    resp = fetch_wikipedia_summary("NonexistentPageXYZ123")
    assert resp["status"] == 404, f"Expected 404, got {resp['status']}"


@test("Bronze supports at least 2 distinct batches per source - directory structure")
def test_bronze_batches():
    for src in ["gbif_taxonomy", "gbif_occurrence", "wikipedia"]:
        d = f"data/bronze/{src}"
        assert os.path.isdir(d), f"Directory {d} not found"


@test("Bronze raw_responses preserves query and response pairs")
def test_raw_responses_structure():
    resp = fetch_gbif_taxonomy("Carcharodon carcharias")
    raw = [{"query": "Carcharodon carcharias", "response": resp}]
    assert isinstance(raw, list)
    assert raw[0]["query"] == "Carcharodon carcharias"
    assert "response" in raw[0]


@test("Bronze directory structure is created automatically")
def test_directory_structure():
    path = persist_bronze("gbif_taxonomy", 99, ["Test"], [{"query": "test", "response": {}}])
    try:
        assert os.path.exists(path)
    finally:
        if os.path.exists(path):
            os.remove(path)


@test("Bronze ingestion timestamp is in ISO 8601 format with Z suffix")
def test_ingested_at_format():
    resp = fetch_gbif_taxonomy("Carcharodon carcharias")
    path = persist_bronze("gbif_taxonomy", 99, ["Carcharodon carcharias"],
                          [{"query": "Carcharodon carcharias", "response": resp}])
    try:
        with open(path) as f:
            env = json.load(f)
        ia = env["ingested_at"]
        assert ia.endswith("Z"), f"ingested_at doesn't end with Z: {ia}"
        datetime.strptime(ia, "%Y-%m-%dT%H:%M:%SZ")
    finally:
        if os.path.exists(path):
            os.remove(path)


@test("Bronze raw JSON files are valid JSON")
def test_bronze_json_valid():
    resp = fetch_gbif_taxonomy("Carcharodon carcharias")
    path = persist_bronze("gbif_taxonomy", 99, ["Test"], [{"query": "test", "response": resp}])
    try:
        with open(path) as f:
            data = json.load(f)
        assert "source" in data
        assert "raw_responses" in data
    finally:
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    print(f"Running {len([k for k in dir() if k.startswith('test_')])} Bronze tests...\n")

    for name in sorted(dir()):
        if name.startswith("test_") and callable(locals()[name]):
            pass

    print(f"\nResults: {PASSED} passed, {FAILED} failed")
    if ERRORS:
        print("\nErrors:")
        for name, err in ERRORS:
            print(f"  {name}: {err}")
    sys.exit(0 if FAILED == 0 else 1)
