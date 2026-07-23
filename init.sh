#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "============================================"
echo "  Shark Knowledge Medallion Architecture"
echo "  Environment Setup"
echo "============================================"

echo ""
echo "[1/4] Creating Python virtual environment with uv..."
if [ ! -d ".venv" ]; then
    uv venv
    echo "  Virtual environment created at .venv"
else
    echo "  Virtual environment already exists"
fi

echo ""
echo "[2/4] Activating virtual environment..."
source .venv/bin/activate

echo ""
echo "[3/4] Installing dependencies with uv..."
uv sync
echo "  Dependencies installed successfully"

echo ""
echo "[4/4] Creating data directories..."
mkdir -p data/bronze/gbif_taxonomy
mkdir -p data/bronze/gbif_occurrence
mkdir -p data/bronze/wikipedia
mkdir -p data/silver/wikipedia/valid
mkdir -p data/silver/wikipedia/rejected
mkdir -p data/silver/gbif_taxonomy/valid
mkdir -p data/silver/gbif_taxonomy/rejected
mkdir -p data/silver/gbif_occurrence/valid
mkdir -p data/silver/gbif_occurrence/rejected
mkdir -p data/gold/faiss_index
echo "  Data directories created"

echo ""
echo "============================================"
echo "  Setup Complete!"
echo "============================================"
echo ""
echo "  Quick Start:"
echo "    source .venv/bin/activate"
echo "    python src/pipeline.py --help"
echo ""
echo "  Run pipeline with seed batch:"
echo "    python src/pipeline.py --batch seed"
echo ""
echo "  Run pipeline with custom species:"
echo "    python src/pipeline.py --species \"Carcharodon carcharias\" \"Rhincodon typus\""
echo ""
echo "  Start Jupyter Lab:"
echo "    jupyter lab --ip=0.0.0.0 --port=8888"
echo ""
echo "  Docker Compose:"
echo "    docker compose up pipeline"
echo "    docker compose up notebook"
echo ""
echo "============================================"
