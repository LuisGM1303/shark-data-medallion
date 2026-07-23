from __future__ import annotations

import json
import os
import re
from datetime import datetime
from enum import Enum
from typing import Any

from src.silver.models import GBIFOccurrence, GBIFTaxonomy, WikipediaPage


class RejectionReason(str, Enum):
    PAGE_NOT_FOUND = "PAGE_NOT_FOUND"
    AMBIGUOUS_RESOLUTION = "AMBIGUOUS_RESOLUTION"
    EXTRACT_TOO_SHORT = "EXTRACT_TOO_SHORT"
    DISAMBIGUATION_PAGE = "DISAMBIGUATION_PAGE"
    HTTP_ERROR = "HTTP_ERROR"
    MISSING_SECTIONS_TEXT = "MISSING_SECTIONS_TEXT"
    MATCH_TYPE_NOT_EXACT = "MATCH_TYPE_NOT_EXACT"
    NO_MATCH_RETURNED = "NO_MATCH_RETURNED"
    MISSING_COORDINATES = "MISSING_COORDINATES"
    COORDINATES_OUT_OF_RANGE = "COORDINATES_OUT_OF_RANGE"
    MISSING_GBIF_ID = "MISSING_GBIF_ID"
    INVALID_EVENT_DATE = "INVALID_EVENT_DATE"
    MISSING_BASIS_OF_RECORD = "MISSING_BASIS_OF_RECORD"


def _save_valid(source: str, key: str, data: dict) -> None:
    path = f"data/silver/{source}/valid/{key}.json"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def _save_rejected(source: str, batch_id: str, key: str, reason: str, context: dict) -> None:
    path = f"data/silver/{source}/rejected/{batch_id}_{source}_{key}.json"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"rejection_reason": reason, "context": context}, f, indent=2, default=str)


def validate_wikipedia(
    data: dict, batch_id: str, species_key: str
) -> dict | None:
    raw = data.get("raw", {})
    summary = raw.get("summary", {})
    extracts_data = raw.get("extracts", {})

    summary_data = summary.get("data") if isinstance(summary, dict) else None
    extracts_data_resp = extracts_data.get("data") if isinstance(extracts_data, dict) else None

    if isinstance(summary, dict) and summary.get("status", 200) != 200:
        _save_rejected(
            "wikipedia", batch_id, species_key, RejectionReason.HTTP_ERROR,
            {"http_status": summary.get("status"), "species_key": species_key},
        )
        return None

    if summary_data is None:
        _save_rejected(
            "wikipedia", batch_id, species_key, RejectionReason.PAGE_NOT_FOUND,
            {"species_key": species_key},
        )
        return None

    title = summary_data.get("title", "")
    extract = summary_data.get("extract", "")
    page_url = summary_data.get("content_urls", {}).get("desktop", {}).get("page", "")
    is_disambig = summary_data.get("type") == "disambiguation"

    if is_disambig:
        _save_rejected(
            "wikipedia", batch_id, species_key, RejectionReason.DISAMBIGUATION_PAGE,
            {"species_key": species_key, "title": title},
        )
        return None

    if len(extract) < 50:
        _save_rejected(
            "wikipedia", batch_id, species_key, RejectionReason.EXTRACT_TOO_SHORT,
            {"species_key": species_key, "extract_length": len(extract)},
        )
        return None

    sections_text = ""
    if extracts_data_resp and isinstance(extracts_data_resp, dict):
        pages = extracts_data_resp.get("query", {}).get("pages", {})
        for pid, pdata in pages.items():
            sections_text = pdata.get("extract", "")
            break

    if not sections_text:
        _save_rejected(
            "wikipedia", batch_id, species_key, RejectionReason.MISSING_SECTIONS_TEXT,
            {"species_key": species_key},
        )
        return None

    resolved_via = data.get("resolved_via", "DIRECT_TITLE")

    try:
        page = WikipediaPage(
            species_key=species_key,
            title=title,
            resolved_via=resolved_via,
            extract=extract,
            sections_text=sections_text,
            page_url=page_url,
            is_disambiguation=False,
        )
    except Exception as e:
        _save_rejected(
            "wikipedia", batch_id, species_key, RejectionReason.HTTP_ERROR,
            {"species_key": species_key, "error": str(e)},
        )
        return None

    result = page.model_dump()
    _save_valid("wikipedia", species_key, result)
    return result


def validate_gbif_taxonomy(
    data: dict, batch_id: str, species_key: str
) -> dict | None:
    raw = data.get("raw", {})
    match_data = raw.get("data") if isinstance(raw, dict) else None
    status = raw.get("status", 200) if isinstance(raw, dict) else 200

    if status != 200:
        _save_rejected(
            "gbif_taxonomy", batch_id, species_key, RejectionReason.HTTP_ERROR,
            {"http_status": status, "species_key": species_key},
        )
        return None

    if not match_data or not isinstance(match_data, dict):
        _save_rejected(
            "gbif_taxonomy", batch_id, species_key, RejectionReason.NO_MATCH_RETURNED,
            {"species_key": species_key},
        )
        return None

    if match_data.get("matchType") != "EXACT":
        _save_rejected(
            "gbif_taxonomy", batch_id, species_key, RejectionReason.MATCH_TYPE_NOT_EXACT,
            {"species_key": species_key, "match_type": match_data.get("matchType")},
        )
        return None

    try:
        tax = GBIFTaxonomy(
            species_key=species_key,
            usage_key=match_data.get("usageKey", 0),
            scientific_name=match_data.get("scientificName", ""),
            canonical_name=match_data.get("canonicalName", ""),
            rank=match_data.get("rank", ""),
            match_type=match_data.get("matchType", ""),
            confidence=match_data.get("confidence", 0),
            kingdom=match_data.get("kingdom"),
            phylum=match_data.get("phylum"),
            class_name=match_data.get("class"),
        )
    except Exception as e:
        _save_rejected(
            "gbif_taxonomy", batch_id, species_key, RejectionReason.HTTP_ERROR,
            {"species_key": species_key, "error": str(e)},
        )
        return None

    result = tax.model_dump()
    _save_valid("gbif_taxonomy", species_key, result)
    return result


def _parse_gbif_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def validate_gbif_occurrence(
    record: dict, batch_id: str, species_key: str
) -> dict | None:
    gbif_id = record.get("gbifID")
    if not gbif_id:
        _save_rejected(
            "gbif_occurrence", batch_id, str(gbif_id), RejectionReason.MISSING_GBIF_ID,
            {"species_key": species_key},
        )
        return None

    lat = record.get("decimalLatitude")
    lon = record.get("decimalLongitude")
    if lat is None or lon is None:
        _save_rejected(
            "gbif_occurrence", batch_id, str(gbif_id), RejectionReason.MISSING_COORDINATES,
            {"species_key": species_key, "gbif_id": gbif_id},
        )
        return None

    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        _save_rejected(
            "gbif_occurrence", batch_id, str(gbif_id), RejectionReason.COORDINATES_OUT_OF_RANGE,
            {"species_key": species_key, "gbif_id": gbif_id, "lat": lat, "lon": lon},
        )
        return None

    if not (-90 <= lat_f <= 90) or not (-180 <= lon_f <= 180):
        _save_rejected(
            "gbif_occurrence", batch_id, str(gbif_id), RejectionReason.COORDINATES_OUT_OF_RANGE,
            {"species_key": species_key, "gbif_id": gbif_id, "lat": lat_f, "lon": lon_f},
        )
        return None

    basis = record.get("basisOfRecord")
    if not basis:
        _save_rejected(
            "gbif_occurrence", batch_id, str(gbif_id), RejectionReason.MISSING_BASIS_OF_RECORD,
            {"species_key": species_key, "gbif_id": gbif_id},
        )
        return None

    event_date = _parse_gbif_date(record.get("eventDate"))
    if record.get("eventDate") and not event_date:
        _save_rejected(
            "gbif_occurrence", batch_id, str(gbif_id), RejectionReason.INVALID_EVENT_DATE,
            {"species_key": species_key, "gbif_id": gbif_id, "event_date": record.get("eventDate")},
        )
        return None

    try:
        occ = GBIFOccurrence(
            gbif_id=int(gbif_id),
            species_key=species_key,
            decimal_latitude=lat_f,
            decimal_longitude=lon_f,
            country=record.get("country"),
            event_date=event_date,
            basis_of_record=basis,
            iucn_red_list_category=record.get("iucnRedListCategory"),
            coordinate_uncertainty_m=(
                float(record["coordinateUncertaintyInMeters"])
                if record.get("coordinateUncertaintyInMeters")
                else None
            ),
        )
    except Exception as e:
        _save_rejected(
            "gbif_occurrence", batch_id, str(gbif_id), RejectionReason.HTTP_ERROR,
            {"species_key": species_key, "gbif_id": gbif_id, "error": str(e)},
        )
        return None

    result = occ.model_dump()
    _save_valid("gbif_occurrence", str(gbif_id), result)
    return result
