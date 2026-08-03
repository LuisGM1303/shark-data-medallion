# Shark Knowledge Medallion Architecture

A deterministic, local-first data pipeline that builds a specialized knowledge base about sharks using a Medallion Architecture (Bronze → Silver → Merge → Warehouse → Gold).

## Architecture Overview

```
GBIF Species Match ──┐
GBIF Occurrence ─────┼──► BRONZE (JSON crudo, timestamped)
Wikipedia (en) ───────┘
            │
            ▼
SILVER (contratos Pydantic + validación)
            │
            ▼
MERGE (Wikipedia = pivote, GBIF = augmentation)
            │
            ▼
WAREHOUSE (DuckDB, UPSERT idempotente)
            │
            ▼
GOLD (Species / SpeciesChunk / FAISS Index)
```

## Data Sources

- **GBIF Species Match API** — taxonomy (kingdom, phylum, class, rank)
- **GBIF Occurrence Search API** — occurrence records (country, coordinates, dates, IUCN)
- **Wikipedia (English)** — summaries and full section extracts

## Technology Stack

- Python 3.12+
- Pydantic v2 (data validation)
- DuckDB (embedded warehouse)
- FAISS IndexHNSWFlat (vector index)
- BAAI/bge-small-en-v1.5 (embeddings, 384 dim)
- uv (package management)
- Docker Compose (deployment)

## Getting Started

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (package manager)
- Docker & Docker Compose (optional, for containerized deployment)

### Local Setup

```bash
chmod +x init.sh
./init.sh
source .venv/bin/activate
```

### Run Pipeline

```bash
# Process seed batch (18 species)
python src/pipeline.py --batch seed

# Process custom species
python src/pipeline.py --species "Carcharodon carcharias" "Rhincodon typus"

# Process from file
python src/pipeline.py --species-file species.txt
```

### Docker

```bash
# Run pipeline
docker compose up pipeline

# Start Jupyter Lab
docker compose up notebook
```

### Search

```python
from src.gold import search

# Basic search
results = search("great white shark diet", top_k=5)

# With filters
results = search(
    "shark habitat",
    filtro_taxonomia={"class_name": "Elasmobranchii"},
    filtro_iucn="VU",
    filtro_pais="South Africa"
)
```

## Project Structure

```
src/
├── bronze/          # GBIF + Wikipedia API connectors, raw JSON persistence
├── silver/          # Pydantic models, validation, rejection handling
├── merge/           # Wikipedia/GBIF augmentation, occurrence aggregation
├── warehouse/       # DuckDB UPSERT operations
├── gold/            # Chunking, embeddings, FAISS index, search()
├── resolver/        # Slugify, Wikipedia title resolution
├── config/          # Seed species, pipeline configuration
└── pipeline.py      # End-to-end orchestration
```

## Features

Complete feature list: `docs/features/feature_list.json`

## License

MIT
