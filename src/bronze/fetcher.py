"""Bronze layer: fetch raw data from GBIF and Wikipedia APIs, persist as-is."""

import json
import os
from datetime import datetime, timezone

import requests


def fetch_gbif_taxonomy(scientific_name: str) -> dict:
    raise NotImplementedError


def fetch_gbif_occurrences(scientific_name: str) -> dict:
    raise NotImplementedError


def fetch_wikipedia_summary(title: str) -> dict:
    raise NotImplementedError


def fetch_wikipedia_extracts(title: str) -> dict:
    raise NotImplementedError


def persist_bronze(source: str, lote: int, species_queried: list[str], raw_responses: list[dict]) -> str:
    raise NotImplementedError
