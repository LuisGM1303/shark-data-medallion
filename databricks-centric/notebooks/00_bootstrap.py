# Databricks notebook source
# MAGIC %md
# MAGIC # Shark Knowledge v2 — Bootstrap
# MAGIC
# MAGIC Installs dependencies, wires the `src/` Python modules into `sys.path`,
# MAGIC and creates the Unity Catalog catalog, schemas and Delta tables.
# MAGIC
# MAGIC **Run this notebook first.** The other notebooks `%run` it to reuse the
# MAGIC setup. Upload the whole `databricks-centric/` folder to your workspace so
# MAGIC that `notebooks/` and `src/` sit side by side.

# Databricks notebook source
# MAGIC %pip install pydantic requests

# Databricks notebook source
import sys


def _workspace_src_root():
    # Returns the workspace path of the folder that contains BOTH notebooks/ and
    # src/ (the parent of the notebook's own directory). Example:
    #   notebook path: /Users/me/databricks-centric/notebooks/00_bootstrap
    #   -> /Workspace/Users/me/databricks-centric
    try:
        ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
        nb_path = ctx.notebookPath().get()
        nb_dir = nb_path.rsplit("/", 1)[0]
        base = nb_dir.rsplit("/", 1)[0]
        return f"/Workspace{base}"
    except Exception:
        return None


SRC_ROOT = _workspace_src_root()
if SRC_ROOT and SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

# If auto-detection failed, uncomment and set your workspace path manually:
# SRC_ROOT = "/Workspace/Users/<your-email>/databricks-centric"
# sys.path.insert(0, SRC_ROOT)

print("SRC_ROOT =", SRC_ROOT)

# Databricks notebook source
try:
    from src.pipeline import run_pipeline
    from src.storage import delta
    from src.config.seed_species import SEED_SPECIES, SEED_SCIENTIFIC_NAMES
except ImportError as e:
    raise RuntimeError(
        "Could not import the src/ modules. Make sure the src/ folder is uploaded "
        "as workspace FILES (not notebooks) and sits next to notebooks/. "
        f"SRC_ROOT={SRC_ROOT}. Original error: {e}"
    )

delta.set_spark(spark)
delta.ensure_schema(spark)

print("Bootstrap complete: catalog/schemas/tables ready.")
