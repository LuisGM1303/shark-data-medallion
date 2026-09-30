"""Bronze fetchers: raw source observations from GBIF and Wikipedia.

Each fetcher returns a raw envelope ``{"status": int, "data": ...}`` that is
persisted verbatim into Bronze Delta tables. No semantic parsing happens here;
Silver owns validation. Errors are data: HTTP errors and empty responses are
returned as-is so they can be persisted.
"""

from __future__ import annotations

import time

import requests

GBIF_SPECIES_MATCH = "https://api.gbif.org/v1/species/match"
GBIF_OCCURRENCE = "https://api.gbif.org/v1/occurrence/search"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
WIKIPEDIA_REST = "https://en.wikipedia.org/api/rest_v1"

_HEADERS = {
    "User-Agent": "SharkKnowledgeMedallion/2.0 (educational project; mailto:example@example.com)"
}


def _retry_wait(resp: requests.Response, attempt: int) -> float:
    retry_after = resp.headers.get("Retry-After")
    if retry_after:
        try:
            return max(1.0, float(retry_after))
        except ValueError:
            pass
    return min(2 ** attempt, 30.0)


def _request_with_retry(
    url: str, params: dict | None = None, max_retries: int = 5, timeout: int = 30
) -> requests.Response:
    resp = None
    for attempt in range(max_retries):
        resp = requests.get(url, params=params, headers=_HEADERS, timeout=timeout)
        if resp.status_code == 429:
            time.sleep(_retry_wait(resp, attempt))
            continue
        return resp
    return resp


def fetch_gbif_taxonomy(scientific_name: str) -> dict:
    resp = _request_with_retry(
        GBIF_SPECIES_MATCH, params={"name": scientific_name}, timeout=30
    )
    return {"status": resp.status_code, "data": resp.json() if resp.ok else resp.text}


def fetch_gbif_occurrences(scientific_name: str) -> dict:
    params = {
        "scientificName": scientific_name,
        "hasCoordinate": "true",
        "limit": 50,
    }
    resp = _request_with_retry(GBIF_OCCURRENCE, params=params, timeout=30)
    return {"status": resp.status_code, "data": resp.json() if resp.ok else resp.text}


def fetch_wikipedia_summary(title: str) -> dict:
    url = f"{WIKIPEDIA_REST}/page/summary/{title.replace(' ', '_')}"
    resp = _request_with_retry(url, timeout=15)
    return {"status": resp.status_code, "data": resp.json() if resp.ok else resp.text}


def fetch_wikipedia_extracts(title: str) -> dict:
    params = {
        "action": "query",
        "prop": "extracts",
        "explaintext": "true",
        "titles": title,
        "format": "json",
    }
    resp = _request_with_retry(WIKIPEDIA_API, params=params, timeout=15)
    return {"status": resp.status_code, "data": resp.json() if resp.ok else resp.text}
