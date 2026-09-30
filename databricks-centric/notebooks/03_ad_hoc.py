# Databricks notebook source
# MAGIC %md
# MAGIC # 03 — Ad-hoc Species
# MAGIC
# MAGIC Processes a species outside the seed set using only its scientific name.
# MAGIC No master allow-list is edited; the species is resolved and processed
# MAGIC through Bronze -> Silver -> Gold with `origin = 'AD_HOC'`.

# Databricks notebook source
# MAGIC %run ./00_bootstrap

# Databricks notebook source
AD_HOC_SPECIES = ["Carcharhinus amblyrhynchos"]  # Grey reef shark

summary = run_pipeline(AD_HOC_SPECIES, batch_id="adhoc_batch_01")

# Databricks notebook source
import json

print(json.dumps(summary, indent=2, default=str))

# Databricks notebook source
# MAGIC %md
# MAGIC ## Verify origin = AD_HOC

# Databricks notebook source
spark.sql("""
    SELECT species_key, scientific_name, wikipedia_title, origin
    FROM shark_knowledge.gold.species
    WHERE scientific_name = 'Carcharhinus amblyrhynchos'
""").show(truncate=False)
