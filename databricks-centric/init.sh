#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "============================================"
echo "  Shark Knowledge v2 — Databricks-Centric"
echo "  Environment Setup"
echo "============================================"
echo ""
echo "This version runs in Databricks Free Edition. There are no local servers."
echo "This script only prepares a local venv for OPTIONAL testing of the"
echo "pure-Python modules (resolver, silver, merge, gold, hashing)."
echo ""

if command -v uv >/dev/null 2>&1; then
    echo "[1/2] Creating local venv with uv (for optional local testing)..."
    if [ ! -d ".venv" ]; then
        uv venv
    fi
    source .venv/bin/activate
    uv pip install pydantic requests pytest >/dev/null 2>&1 || true
    echo "  Local venv ready (pydantic, requests, pytest)."
else
    echo "[1/2] uv not found — skipping local venv (not required for Databricks)."
fi

echo ""
echo "[2/2] Verifying project structure..."
for d in src/config src/resolver src/bronze src/silver src/merge src/gold src/storage notebooks; do
    if [ -d "$d" ]; then
        echo "  OK  $d/"
    else
        echo "  MISSING  $d/"
    fi
done

echo ""
echo "============================================"
echo "  Setup Complete!"
echo "============================================"
echo ""
echo "  To run in Databricks Free Edition:"
echo "    1. Create a folder in your workspace (e.g. databricks-centric)."
echo "    2. Upload src/ and notebooks/ into it, side by side."
echo "    3. Run notebooks/00_bootstrap.py first."
echo "    4. Then run 01_run_pipeline.py, 02_verify_data.py, etc."
echo ""
echo "  Optional local smoke test of pure-Python modules:"
echo "    source .venv/bin/activate"
echo "    python -c \"from src.resolver.slugify import slugify; print(slugify('Prionace glauca'))\""
echo ""
echo "============================================"
