# Databricks notebook source
# MAGIC %md
# MAGIC # 04 — Quarantine
# MAGIC
# MAGIC Demonstrates that a species with invalid Wikipedia resolution does NOT
# MAGIC enter Gold, and that the rejection remains inspectable in
# MAGIC `shark_knowledge.silver.rejected_records`.

# Databricks notebook source
# MAGIC %run ./00_bootstrap

# Databricks notebook source
INVALID_SPECIES = ["Nonexistentus sharkus"]  # no Wikipedia article

summary = run_pipeline(INVALID_SPECIES, batch_id="quarantine_batch_01")

# Databricks notebook source
import json

print(json.dumps(summary, indent=2, default=str))

# Databricks notebook source
# MAGIC %md
# MAGIC ## Verify the species did NOT enter Gold

# Databricks notebook source
n = spark.sql("""
    SELECT COUNT(*) AS n
    FROM shark_knowledge.gold.species
    WHERE species_key = 'nonexistentus_sharkus'
""").collect()[0]["n"]

print("gold.species rows for invalid species =", n, "(expected 0)")
assert n == 0, "invalid species must not enter Gold"

# Databricks notebook source
# MAGIC %md
# MAGIC ## Inspect the quarantine record

# Databricks notebook source
spark.sql("""
    SELECT rejection_id, source, species_key, rejection_reason, rejection_detail, rejected_at
    FROM shark_knowledge.silver.rejected_records
    WHERE species_key = 'nonexistentus_sharkus'
""").show(truncate=False)
