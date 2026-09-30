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


def _workspace_src_path():
    try:
        ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
        nb_path = ctx.notebookPath().get()
        base = nb_path.rsplit("/notebooks/", 1)[0]
        return f"/Workspace{base}/src"
    except Exception:
        return None


SRC_PATH = _workspace_src_path()
if SRC_PATH and SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

# If auto-detection failed, uncomment and set your workspace path manually:
# SRC_PATH = "/Workspace/Users/<your-email>/databricks-centric/src"
# sys.path.insert(0, SRC_PATH)

print("SRC_PATH =", SRC_PATH)

# Databricks notebook source
from src.pipeline import run_pipeline
from src.storage import delta
from src.config.seed_species import SEED_SPECIES, SEED_SCIENTIFIC_NAMES

delta.set_spark(spark)
delta.ensure_schema(spark)

print("Bootstrap complete: catalog/schemas/tables ready.")
