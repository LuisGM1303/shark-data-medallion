from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import requests

GBIF_SPECIES_MATCH = "https://api.gbif.org/v1/species/match"
GBIF_OCCURRENCE = "https://api.gbif.org/v1/occurrence/search"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
WIKIPEDIA_REST = "https://en.wikipedia.org/api/rest_v1"

_HEADERS = {
    "User-Agent": "SharkKnowledgeMedallion/1.0 (educational project; mailto:example@example.com)"
}


def fetch_gbif_taxonomy(scientific_name: str) -> dict:
    resp = requests.get(
        GBIF_SPECIES_MATCH, params={"name": scientific_name}, headers=_HEADERS, timeout=30
    )
    return {"status": resp.status_code, "data": resp.json() if resp.ok else resp.text}


def fetch_gbif_occurrences(scientific_name: str) -> dict:
    params = {
        "scientificName": scientific_name,
        "hasCoordinate": "true",
        "limit": 50,
    }
    resp = requests.get(
        GBIF_OCCURRENCE, params=params, headers=_HEADERS, timeout=30
    )
    return {"status": resp.status_code, "data": resp.json() if resp.ok else resp.text}


def fetch_wikipedia_summary(title: str) -> dict:
    url = f"{WIKIPEDIA_REST}/page/summary/{title.replace(' ', '_')}"
    resp = requests.get(url, headers=_HEADERS, timeout=15)
    return {"status": resp.status_code, "data": resp.json() if resp.ok else resp.text}


def fetch_wikipedia_extracts(title: str) -> dict:
    params = {
        "action": "query",
        "prop": "extracts",
        "explaintext": "true",
        "titles": title,
        "format": "json",
    }
    resp = requests.get(WIKIPEDIA_API, params=params, headers=_HEADERS, timeout=15)
    return {"status": resp.status_code, "data": resp.json() if resp.ok else resp.text}


def persist_bronze(
    source: str, lote: int, species_queried: list[str], raw_responses: list[dict]
) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    filename = f"lote_{lote}__{timestamp}.json"

    base_dir = f"data/bronze/{source}"
    os.makedirs(base_dir, exist_ok=True)
    path = os.path.join(base_dir, filename)

    envelope = {
        "source": source,
        "lote": lote,
        "ingested_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "species_queried": species_queried,
        "raw_responses": raw_responses,
    }

    with open(path, "w") as f:
        json.dump(envelope, f, indent=2, default=str)

    return path
