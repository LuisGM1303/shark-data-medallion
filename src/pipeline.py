from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from src.resolver.slugify import slugify
from src.resolver.wikipedia import (
    resolve_wikipedia_title,
    ResolutionMethod,
    ResolutionStatus,
)
from src.bronze.fetcher import (
    fetch_gbif_taxonomy,
    fetch_gbif_occurrences,
    fetch_wikipedia_summary,
    fetch_wikipedia_extracts,
    persist_bronze,
)
from src.silver.validator import (
    validate_wikipedia,
    validate_gbif_taxonomy,
    validate_gbif_occurrence,
)
from src.merge.merger import merge_species
from src.warehouse.loader import Warehouse
from src.gold.indexer import (
    build_species_from_merged,
    chunk_species,
    build_metadata,
    embed_chunks,
    build_faiss_index,
    save_index,
)
from src.config.seed_species import SEED_SPECIES

import os


def _save_wikipedia_rejected(batch_id: str, species_key: str, reason: str, context: dict) -> None:
    path = f"data/silver/wikipedia/rejected/{batch_id}_wikipedia_{species_key}.json"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"rejection_reason": reason, "context": context}, f, indent=2, default=str)


def _get_seed_origin(scientific_name: str) -> str:
    return "SEED" if any(s["scientific_name"] == scientific_name for s in SEED_SPECIES) else "AD_HOC"


def run_pipeline(species_names: list[str], batch_id: str | None = None) -> dict:
    if not species_names:
        return {"status": "empty_batch", "message": "No species provided"}

    if batch_id is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        batch_id = f"batch_{ts}"

    summary: dict = {
        "batch_id": batch_id,
        "n_species": len(species_names),
        "bronze": {"gbif_taxonomy": [], "gbif_occurrence": [], "wikipedia": []},
        "silver": {
            "wikipedia_valid": 0, "wikipedia_rejected": 0,
            "gbif_taxonomy_valid": 0, "gbif_taxonomy_rejected": 0,
            "gbif_occurrence_valid": 0, "gbif_occurrence_rejected": 0,
        },
        "merge": {"merged": 0, "skipped_no_wikipedia": 0},
        "warehouse": {},
        "gold": {},
    }

    wh = Warehouse()
    wh.connect()
    wh.initialize_schema()

    all_silver_wikipedia: list[dict] = []
    all_silver_gbif_taxonomy: list[dict] = []
    all_silver_gbif_occurrences_by_sk: dict[str, list[dict]] = {}
    all_merged: list[dict] = []
    all_species_catalog: list[dict] = []

    for sci_name in species_names:
        sk = slugify(sci_name)

        gbif_tax_raw = fetch_gbif_taxonomy(sci_name)
        gbif_occ_raw = fetch_gbif_occurrences(sci_name)

        resolution = resolve_wikipedia_title(sci_name)

        if resolution.status in (
            ResolutionStatus.PAGE_NOT_FOUND,
            ResolutionStatus.AMBIGUOUS_RESOLUTION,
            ResolutionStatus.DISAMBIGUATION_PAGE,
        ):
            summary["silver"]["wikipedia_rejected"] += 1

            gbif_tax_responses = [{"query": sci_name, "response": gbif_tax_raw}]
            gbif_occ_responses = [{"query": sci_name, "response": gbif_occ_raw}]

            persist_bronze("gbif_taxonomy", 1, [sci_name], gbif_tax_responses)
            persist_bronze("gbif_occurrence", 1, [sci_name], gbif_occ_responses)

            rejection_context = {
                "species_key": sk,
                "scientific_name": sci_name,
                "resolution_status": resolution.status.value,
            }
            if resolution.candidates:
                rejection_context["candidates"] = resolution.candidates
            if resolution.title:
                rejection_context["title"] = resolution.title

            _save_wikipedia_rejected(batch_id, sk, resolution.status.value, rejection_context)
            continue

        wp_title = resolution.title
        wp_search = resolution.resolved_via == ResolutionMethod.SEARCH

        wp_summary = fetch_wikipedia_summary(wp_title)
        wp_extracts = fetch_wikipedia_extracts(wp_title)

        lote = 1
        species_queried_gbif_tax = [sci_name]
        species_queried_gbif_occ = [sci_name]
        species_queried_wp = [wp_title]

        gbif_tax_responses = [{"query": sci_name, "response": gbif_tax_raw}]
        gbif_occ_responses = [{"query": sci_name, "response": gbif_occ_raw}]
        wp_responses = [
            {"query": f"summary:{wp_title}", "response": wp_summary},
            {"query": f"extracts:{wp_title}", "response": wp_extracts},
        ]

        bronze_tax_path = persist_bronze("gbif_taxonomy", lote, species_queried_gbif_tax, gbif_tax_responses)
        bronze_occ_path = persist_bronze("gbif_occurrence", lote, species_queried_gbif_occ, gbif_occ_responses)
        bronze_wp_path = persist_bronze("wikipedia", lote, species_queried_wp, wp_responses)

        summary["bronze"]["gbif_taxonomy"].append(bronze_tax_path)
        summary["bronze"]["gbif_occurrence"].append(bronze_occ_path)
        summary["bronze"]["wikipedia"].append(bronze_wp_path)

        validated_wp = validate_wikipedia(
            {
                "raw": {"summary": wp_summary, "extracts": wp_extracts},
                "resolved_via": resolution.resolved_via.value if resolution.resolved_via else "SEARCH",
            },
            batch_id,
            sk,
        )
        if validated_wp:
            summary["silver"]["wikipedia_valid"] += 1
            all_silver_wikipedia.append(validated_wp)
        else:
            summary["silver"]["wikipedia_rejected"] += 1

        validated_tax = validate_gbif_taxonomy(
            {"raw": gbif_tax_raw},
            batch_id,
            sk,
        )
        if validated_tax:
            summary["silver"]["gbif_taxonomy_valid"] += 1
            all_silver_gbif_taxonomy.append(validated_tax)
        else:
            summary["silver"]["gbif_taxonomy_rejected"] += 1

        occ_results = []
        if isinstance(gbif_occ_raw.get("data"), dict):
            for record in gbif_occ_raw["data"].get("results", []):
                validated_occ = validate_gbif_occurrence(record, batch_id, sk)
                if validated_occ:
                    occ_results.append(validated_occ)
                    summary["silver"]["gbif_occurrence_valid"] += 1
                else:
                    summary["silver"]["gbif_occurrence_rejected"] += 1
        all_silver_gbif_occurrences_by_sk[sk] = occ_results

        if validated_wp:
            merged = merge_species(validated_wp, validated_tax, occ_results)
            if merged:
                summary["merge"]["merged"] += 1
                merged_dict = merged.model_dump()
                all_merged.append(merged_dict)
                all_species_catalog.append({
                    "species_key": sk,
                    "scientific_name": sci_name,
                    "wikipedia_title": merged.wikipedia_title,
                    "origin": _get_seed_origin(sci_name),
                })
        else:
            summary["merge"]["skipped_no_wikipedia"] += 1

    wh.upsert_wikipedia(all_silver_wikipedia)
    wh.upsert_gbif_taxonomy(all_silver_gbif_taxonomy)
    for sk, occs in all_silver_gbif_occurrences_by_sk.items():
        wh.upsert_gbif_occurrences(occs)
    wh.upsert_species_merged(all_merged)
    wh.upsert_species_catalog(all_species_catalog, batch_id)

    evidence = wh.get_evidence()
    summary["warehouse"] = evidence

    all_chunks: list[dict] = []
    for merged in all_merged:
        species = build_species_from_merged(merged)
        chunks = chunk_species(species)
        all_chunks.extend(chunks)

    if all_chunks:
        embeddings = embed_chunks(all_chunks)
        index = build_faiss_index(embeddings)
        save_index(index, all_chunks)
        summary["gold"] = {
            "n_species": len(all_merged),
            "n_chunks": len(all_chunks),
            "index_size": index.ntotal,
        }
    else:
        summary["gold"] = {"n_species": 0, "n_chunks": 0, "index_size": 0}

    return summary


def main():
    parser = argparse.ArgumentParser(description="Shark Knowledge Medallion Pipeline")
    parser.add_argument("--batch", choices=["seed"], help="Run with seed species batch")
    parser.add_argument("--species", nargs="+", help="List of scientific names to process")
    parser.add_argument("--species-file", type=str, help="File with species names (one per line)")
    args = parser.parse_args()

    if args.batch == "seed":
        species = [s["scientific_name"] for s in SEED_SPECIES]
    elif args.species:
        species = args.species
    elif args.species_file:
        with open(args.species_file) as f:
            species = [line.strip() for line in f if line.strip()]
    else:
        parser.print_help()
        sys.exit(1)

    result = run_pipeline(species)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
