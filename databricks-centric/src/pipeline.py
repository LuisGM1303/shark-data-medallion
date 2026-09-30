"""End-to-end orchestration: Bronze -> Silver -> Gold (Databricks-centric).

Receives a list of scientific names (seed batch, ad-hoc, or a mix) and drives
the full medallion pipeline, persisting to governed Delta tables in Unity
Catalog. Business logic lives in the resolver/bronze/silver/merge/gold modules;
this module only orchestrates and assembles operational fields.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone

from src.bronze.fetcher import (
    fetch_gbif_occurrences,
    fetch_gbif_taxonomy,
    fetch_wikipedia_extracts,
    fetch_wikipedia_summary,
)
from src.config.seed_species import SEED_SCIENTIFIC_NAMES
from src.gold.chunker import (
    build_document_text,
    build_species_from_merged,
    chunk_species,
)
from src.gold.models import SECTION_ATTR
from src.merge.merger import merge_species
from src.resolver.slugify import slugify
from src.resolver.wikipedia import (
    ResolutionStatus,
    resolve_wikipedia_title,
)
from src.silver.validator import (
    validate_gbif_occurrence,
    validate_gbif_taxonomy,
    validate_wikipedia,
)
from src.storage import delta
from src.storage.hashing import content_hash, record_hash, rejection_id

_RESOLUTION_REJECTIONS = {
    ResolutionStatus.PAGE_NOT_FOUND,
    ResolutionStatus.AMBIGUOUS_RESOLUTION,
    ResolutionStatus.DISAMBIGUATION_PAGE,
}

# Polite delay between species to stay under Wikipedia's rate limit.
REQUEST_DELAY_SECONDS = 1.0


def _ingestion_id(run_id: str, source: str, species_key: str) -> str:
    return f"{run_id}__{source}__{species_key}"


def _add_silver_ops(valid_record: dict, source_ingestion_id: str, validated_at: datetime) -> dict:
    rec = dict(valid_record)
    rec["content_hash"] = content_hash(rec)
    rec["source_ingestion_id"] = source_ingestion_id
    rec["validated_at"] = validated_at
    return rec


def _finalize_rejection(
    rej: dict,
    run_id: str,
    batch_id: str,
    source_ingestion_id: str | None,
    rejected_at: datetime,
) -> dict:
    rh = record_hash(rej["record_payload"])
    rid = rejection_id(rej["source"], rej["natural_key"], rej["rejection_reason"], rh)
    return {
        "rejection_id": rid,
        "run_id": run_id,
        "batch_id": batch_id,
        "source": rej["source"],
        "species_key": rej["species_key"],
        "natural_key": rej["natural_key"],
        "rejection_reason": rej["rejection_reason"],
        "rejection_detail": rej["rejection_detail"],
        "record_payload": rej["record_payload"],
        "record_hash": rh,
        "source_ingestion_id": source_ingestion_id,
        "rejected_at": rejected_at,
    }


def run_pipeline(
    species_names: list[str],
    batch_id: str | None = None,
    run_id: str | None = None,
    spark=None,
) -> dict:
    if spark is None:
        spark = delta._get_spark()
    delta.set_spark(spark)
    delta.ensure_schema(spark)

    if not species_names:
        return {"status": "empty_batch", "message": "No species provided"}

    if batch_id is None:
        batch_id = f"batch_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
    if run_id is None:
        run_id = str(uuid.uuid4())

    now = datetime.now(timezone.utc)

    bronze_wikipedia: list[dict] = []
    bronze_taxonomy: list[dict] = []
    bronze_occurrence: list[dict] = []
    silver_wikipedia: list[dict] = []
    silver_taxonomy: list[dict] = []
    silver_occurrences: list[dict] = []
    rejected: list[dict] = []
    merged_rows: list[dict] = []
    silver_wikipedia_by_sk: dict[str, dict] = {}
    scientific_name_by_sk: dict[str, str] = {}

    counts = {
        "wikipedia_valid": 0, "wikipedia_rejected": 0,
        "gbif_taxonomy_valid": 0, "gbif_taxonomy_rejected": 0,
        "gbif_occurrence_valid": 0, "gbif_occurrence_rejected": 0,
    }

    for i, sci_name in enumerate(species_names):
        if i > 0:
            time.sleep(REQUEST_DELAY_SECONDS)
        sk = slugify(sci_name)
        scientific_name_by_sk[sk] = sci_name

        gbif_tax_raw = fetch_gbif_taxonomy(sci_name)
        gbif_occ_raw = fetch_gbif_occurrences(sci_name)

        tax_ingestion_id = _ingestion_id(run_id, "gbif_taxonomy", sk)
        occ_ingestion_id = _ingestion_id(run_id, "gbif_occurrence", sk)

        bronze_taxonomy.append({
            "ingestion_id": tax_ingestion_id,
            "run_id": run_id,
            "batch_id": batch_id,
            "species_key": sk,
            "scientific_name": sci_name,
            "raw_payload": json.dumps(gbif_tax_raw, default=str),
            "ingested_at": now,
        })
        bronze_occurrence.append({
            "ingestion_id": occ_ingestion_id,
            "run_id": run_id,
            "batch_id": batch_id,
            "species_key": sk,
            "scientific_name": sci_name,
            "raw_payload": json.dumps(gbif_occ_raw, default=str),
            "ingested_at": now,
        })

        resolution = resolve_wikipedia_title(sci_name)

        if resolution.status in _RESOLUTION_REJECTIONS:
            counts["wikipedia_rejected"] += 1
            detail = None
            if resolution.candidates:
                detail = f"candidates={resolution.candidates}"
            rej = {
                "source": "wikipedia",
                "species_key": sk,
                "natural_key": sk,
                "rejection_reason": resolution.status.value,
                "rejection_detail": detail,
                "record_payload": json.dumps({
                    "scientific_name": sci_name,
                    "resolution_status": resolution.status.value,
                    "candidates": resolution.candidates,
                    "title": resolution.title,
                }, default=str),
            }
            rejected.append(_finalize_rejection(rej, run_id, batch_id, None, now))
            continue

        wp_title = resolution.title
        wp_summary = fetch_wikipedia_summary(wp_title)
        wp_extracts = fetch_wikipedia_extracts(wp_title)

        wp_ingestion_id = _ingestion_id(run_id, "wikipedia", sk)
        bronze_wikipedia.append({
            "ingestion_id": wp_ingestion_id,
            "run_id": run_id,
            "batch_id": batch_id,
            "species_key": sk,
            "scientific_name": sci_name,
            "raw_payload": json.dumps({"summary": wp_summary, "extracts": wp_extracts}, default=str),
            "ingested_at": now,
        })

        resolved_via = resolution.resolved_via.value if resolution.resolved_via else "SEARCH"
        wp_valid, wp_rej = validate_wikipedia(
            {"raw": {"summary": wp_summary, "extracts": wp_extracts}, "resolved_via": resolved_via},
            sk,
        )
        if wp_valid:
            counts["wikipedia_valid"] += 1
            silver_wikipedia.append(_add_silver_ops(wp_valid, wp_ingestion_id, now))
            silver_wikipedia_by_sk[sk] = wp_valid
        else:
            counts["wikipedia_rejected"] += 1
            rejected.append(_finalize_rejection(wp_rej, run_id, batch_id, wp_ingestion_id, now))

        tax_valid, tax_rej = validate_gbif_taxonomy({"raw": gbif_tax_raw}, sk)
        if tax_valid:
            counts["gbif_taxonomy_valid"] += 1
            silver_taxonomy.append(_add_silver_ops(tax_valid, tax_ingestion_id, now))
        else:
            counts["gbif_taxonomy_rejected"] += 1
            rejected.append(_finalize_rejection(tax_rej, run_id, batch_id, tax_ingestion_id, now))

        occ_valid_list: list[dict] = []
        if isinstance(gbif_occ_raw.get("data"), dict):
            for record in gbif_occ_raw["data"].get("results", []):
                occ_valid, occ_rej = validate_gbif_occurrence(record, sk)
                if occ_valid:
                    counts["gbif_occurrence_valid"] += 1
                    occ_valid_list.append(occ_valid)
                    silver_occurrences.append(_add_silver_ops(occ_valid, occ_ingestion_id, now))
                else:
                    counts["gbif_occurrence_rejected"] += 1
                    rejected.append(_finalize_rejection(occ_rej, run_id, batch_id, occ_ingestion_id, now))

        if wp_valid:
            merged = merge_species(wp_valid, tax_valid, occ_valid_list)
            if merged:
                merged_rows.append(merged.model_dump())

    # Persist Bronze (append-only).
    delta.append_wikipedia_bronze(spark, bronze_wikipedia)
    delta.append_gbif_taxonomy_bronze(spark, bronze_taxonomy)
    delta.append_gbif_occurrence_bronze(spark, bronze_occurrence)

    # Persist Silver (MERGE).
    delta.merge_wikipedia_silver(spark, silver_wikipedia)
    delta.merge_gbif_taxonomy_silver(spark, silver_taxonomy)
    delta.merge_gbif_occurrences_silver(spark, silver_occurrences)
    delta.merge_rejected_records(spark, rejected)

    # Build and persist Gold (MERGE).
    species_rows: list[dict] = []
    chunk_rows: list[dict] = []
    for merged in merged_rows:
        sk = merged["species_key"]
        sci_name = scientific_name_by_sk.get(sk, merged.get("wikipedia_title", ""))
        page_url = silver_wikipedia_by_sk.get(sk, {}).get("page_url", "")
        origin = "SEED" if sci_name in SEED_SCIENTIFIC_NAMES else "AD_HOC"

        species_dict = build_species_from_merged(merged)
        document_text = build_document_text(species_dict)

        business = {
            "species_key": sk,
            "scientific_name": sci_name,
            "wikipedia_title": merged.get("wikipedia_title", ""),
            "document_uri": page_url,
            "document_text": document_text,
            "kingdom": merged.get("kingdom"),
            "phylum": merged.get("phylum"),
            "class_name": merged.get("class_name"),
            "rank": merged.get("rank"),
            "taxonomy_status": merged.get("taxonomy_status", "UNMATCHED"),
            "iucn_red_list_category": merged.get("iucn_red_list_category"),
            "countries": merged.get("paises", []),
            "year_min": merged.get("anio_min"),
            "year_max": merged.get("anio_max"),
            "n_valid_occurrences": merged.get("n_occurrences_validas", 0),
            "augmentation_status": merged.get("augmentation_status", "GBIF_AUGMENTATION_EMPTY"),
        }
        for canonical, attr in SECTION_ATTR.items():
            business[attr] = species_dict.get(attr)

        species_content_hash = content_hash(business)
        species_rows.append({
            **business,
            "origin": origin,
            "first_processed_at": now,
            "last_content_change_at": now,
            "content_hash": species_content_hash,
        })

        for ch in chunk_species(species_dict, merged, sci_name, page_url):
            ch_content_hash = content_hash(ch)
            chunk_rows.append({
                **ch,
                "parent_content_hash": species_content_hash,
                "content_hash": ch_content_hash,
                "last_content_change_at": now,
            })

    delta.merge_species(spark, species_rows)
    delta.merge_species_chunks(spark, chunk_rows)

    return {
        "batch_id": batch_id,
        "run_id": run_id,
        "n_species": len(species_names),
        "bronze": {
            "wikipedia": len(bronze_wikipedia),
            "gbif_taxonomy": len(bronze_taxonomy),
            "gbif_occurrence": len(bronze_occurrence),
        },
        "silver": counts,
        "rejected_records": len(rejected),
        "gold": {
            "species": len(species_rows),
            "chunks": len(chunk_rows),
        },
    }
