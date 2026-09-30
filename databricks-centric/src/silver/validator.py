"""Silver validation: Pydantic contracts + explicit rejection reasons.

Each validator returns a tuple ``(valid_record, rejection_record)`` where
exactly one of the two is non-None. Valid records contain business fields
only; operational fields (content_hash, validated_at, source_ingestion_id)
are added by the pipeline. Rejection records carry the reason, detail and
the raw payload so the quarantine table remains fully auditable.
"""

from __future__ import annotations

import json
from datetime import datetime

from src.silver.models import GBIFOccurrence, GBIFTaxonomy, WikipediaPage

# Rejection reasons (preserved from v1).
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


def _rejection(source: str, species_key: str | None, natural_key: str | None,
               reason: str, detail: str | None, payload: object) -> dict:
    return {
        "source": source,
        "species_key": species_key,
        "natural_key": natural_key,
        "rejection_reason": reason,
        "rejection_detail": detail,
        "record_payload": json.dumps(payload, default=str),
    }


def validate_wikipedia(data: dict, species_key: str) -> tuple[dict | None, dict | None]:
    raw = data.get("raw", {})
    summary = raw.get("summary", {})
    extracts_data = raw.get("extracts", {})

    summary_data = summary.get("data") if isinstance(summary, dict) else None
    extracts_data_resp = extracts_data.get("data") if isinstance(extracts_data, dict) else None
    status = summary.get("status", 200) if isinstance(summary, dict) else 200

    def reject(reason: str, detail: str | None) -> tuple[None, dict]:
        return None, _rejection(
            "wikipedia", species_key, species_key, reason, detail,
            {"summary": summary, "extracts": extracts_data},
        )

    if status != 200:
        reason = PAGE_NOT_FOUND if status == 404 else HTTP_ERROR
        return reject(reason, f"http_status={status}")

    if summary_data is None:
        return reject(PAGE_NOT_FOUND, "no summary data")

    title = summary_data.get("title", "")
    extract = summary_data.get("extract", "")
    page_url = summary_data.get("content_urls", {}).get("desktop", {}).get("page", "")
    is_disambig = summary_data.get("type") == "disambiguation"

    if is_disambig:
        return reject(DISAMBIGUATION_PAGE, f"title={title}")

    if len(extract) < 50:
        return reject(EXTRACT_TOO_SHORT, f"extract_length={len(extract)}")

    sections_text = ""
    if extracts_data_resp and isinstance(extracts_data_resp, dict):
        pages = extracts_data_resp.get("query", {}).get("pages", {})
        for _pid, pdata in pages.items():
            sections_text = pdata.get("extract", "")
            break

    if not sections_text:
        return reject(MISSING_SECTIONS_TEXT, "no sections text")

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
    except Exception as e:  # noqa: BLE001
        return reject(HTTP_ERROR, str(e))

    return page.model_dump(), None


def validate_gbif_taxonomy(data: dict, species_key: str) -> tuple[dict | None, dict | None]:
    raw = data.get("raw", {})
    match_data = raw.get("data") if isinstance(raw, dict) else None
    status = raw.get("status", 200) if isinstance(raw, dict) else 200

    def reject(reason: str, detail: str | None) -> tuple[None, dict]:
        return None, _rejection(
            "gbif_taxonomy", species_key, species_key, reason, detail, raw,
        )

    if status != 200:
        return reject(HTTP_ERROR, f"http_status={status}")

    if not match_data or not isinstance(match_data, dict):
        return reject(NO_MATCH_RETURNED, "no match returned")

    if match_data.get("matchType") != "EXACT":
        return reject(MATCH_TYPE_NOT_EXACT, f"match_type={match_data.get('matchType')}")

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
    except Exception as e:  # noqa: BLE001
        return reject(HTTP_ERROR, str(e))

    return tax.model_dump(), None


def _parse_gbif_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def validate_gbif_occurrence(record: dict, species_key: str) -> tuple[dict | None, dict | None]:
    gbif_id = record.get("gbifID")
    natural_key = str(gbif_id) if gbif_id else None

    def reject(reason: str, detail: str | None) -> tuple[None, dict]:
        return None, _rejection(
            "gbif_occurrence", species_key, natural_key, reason, detail, record,
        )

    if not gbif_id:
        return reject(MISSING_GBIF_ID, "gbifID missing")

    lat = record.get("decimalLatitude")
    lon = record.get("decimalLongitude")
    if lat is None or lon is None:
        return reject(MISSING_COORDINATES, f"gbif_id={gbif_id}")

    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return reject(COORDINATES_OUT_OF_RANGE, f"lat={lat}, lon={lon}")

    if not (-90 <= lat_f <= 90) or not (-180 <= lon_f <= 180):
        return reject(COORDINATES_OUT_OF_RANGE, f"lat={lat_f}, lon={lon_f}")

    basis = record.get("basisOfRecord")
    if not basis:
        return reject(MISSING_BASIS_OF_RECORD, f"gbif_id={gbif_id}")

    event_date = _parse_gbif_date(record.get("eventDate"))
    if record.get("eventDate") and not event_date:
        return reject(INVALID_EVENT_DATE, f"event_date={record.get('eventDate')}")

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
    except Exception as e:  # noqa: BLE001
        return reject(HTTP_ERROR, str(e))

    return occ.model_dump(), None
