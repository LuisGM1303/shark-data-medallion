# Shark Knowledge v2 — Databricks-Centric

Databricks-native evolution of the Shark Knowledge medallion architecture.
This folder is the **Databricks-centric** version of the project: everything
runs in Databricks Free Edition via thin notebooks, while the business logic
lives in plain Python modules under `src/`.

```
External APIs (Wikipedia + GBIF)
        |
        v
Custom Python ingestion (src/)
        |
        v
BRONZE DELTA  (append-only raw tables)
        |
        v
Pydantic validation
        |
        v
SILVER DELTA  (validated + quarantine tables)
        |
        v
Python knowledge integration
        |
        v
GOLD DELTA    (species + species_chunks)
        |
        v
DATA READY
```

## What changed from v1

| v1 (local) | v2 (Databricks) |
| --- | --- |
| Bronze JSON files | `shark_knowledge.bronze.*` Delta tables (append-only) |
| Silver JSON valid/rejected files | `shark_knowledge.silver.*` Delta tables (MERGE) |
| DuckDB warehouse | Delta managed tables in Unity Catalog |
| `species_catalog` table | `gold.species` (single accepted-species product) |
| FAISS + local embeddings | deferred to Databricks AI Search (future milestone) |
| Docker Compose + Jupyter Lab | Databricks notebooks |

Domain behavior (slugify, Wikipedia resolution, Pydantic contracts, rejection
reasons, Wikipedia pivot, GBIF augmentation, occurrence aggregation, semantic
chunking) is preserved.

## Unity Catalog layout

```
shark_knowledge
├── bronze
│   ├── wikipedia_raw
│   ├── gbif_taxonomy_raw
│   └── gbif_occurrence_raw
├── silver
│   ├── wikipedia_pages
│   ├── gbif_taxonomy
│   ├── gbif_occurrences
│   └── rejected_records
└── gold
    ├── species
    └── species_chunks
```

## Project structure

```
databricks-centric/
├── src/
│   ├── config/seed_species.py   # 18 seed species + catalog/schema constants
│   ├── resolver/                # slugify + Wikipedia title resolution
│   ├── bronze/fetcher.py        # GBIF + Wikipedia API connectors
│   ├── silver/                  # Pydantic models + validators
│   ├── merge/merger.py          # Wikipedia pivot + GBIF augmentation
│   ├── gold/                    # canonical Species + semantic chunking
│   ├── storage/                 # Delta persistence + content hashing
│   └── pipeline.py              # end-to-end orchestration
└── notebooks/
    ├── 00_bootstrap.py          # deps + sys.path + catalog/schema setup
    ├── 01_run_pipeline.py       # run the 18-species seed batch
    ├── 02_verify_data.py        # Data Ready acceptance criteria
    ├── 03_ad_hoc.py             # process a species outside the seed set
    └── 04_quarantine.py         # invalid Wikipedia -> quarantine
```

## Running in Databricks Free Edition

1. In your Databricks workspace, create a folder (e.g. `databricks-centric`).
2. Upload the `src/` and `notebooks/` folders into it, side by side.
3. Open `notebooks/00_bootstrap.py` and run it. It installs `pydantic` and
   `requests`, wires `src/` into `sys.path`, and creates the catalog, schemas
   and Delta tables.
4. Run `01_run_pipeline.py` to process the seed batch.
5. Run `02_verify_data.py` to check the Data Ready acceptance criteria.
6. Run `03_ad_hoc.py` and `04_quarantine.py` for the ad-hoc and quarantine demos.

> **Outbound internet:** Free Edition restricts outbound internet by default.
> Verify that Wikipedia and GBIF are reachable from your workspace before the
> first run (see `02_verify_data.py` / a simple `requests.get` smoke test).

## Local development (optional)

The pure-Python modules (resolver, silver, merge, gold, hashing) have no Spark
dependency and can be tested locally:

```bash
cd databricks-centric
./init.sh            # creates a local venv for testing
source .venv/bin/activate
python -c "from src.resolver.slugify import slugify; print(slugify('Prionace glauca'))"
```

`storage/delta.py` and `pipeline.py` require a Spark session and are exercised
inside Databricks.

## Feature list

The single source of truth for what must be built and verified is
`docs/features/v2_evolution_feature_list.json` (224 end-to-end test cases).
