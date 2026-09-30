# Databricks notebook source
# MAGIC %md
# MAGIC # 02 — Verify Data (Data Ready acceptance criteria)
# MAGIC
# MAGIC Verifies the Data Ready acceptance criteria from SAS v2 section 19:
# MAGIC populated Bronze/Silver, exactly 18 accepted `gold.species`, deterministic
# MAGIC chunks, and rerun convergence.

# Databricks notebook source
# MAGIC %run ./00_bootstrap

# Databricks notebook source
# MAGIC %md
# MAGIC ## 1. Table inventory

# Databricks notebook source
tables = [
    "shark_knowledge.bronze.wikipedia_raw",
    "shark_knowledge.bronze.gbif_taxonomy_raw",
    "shark_knowledge.bronze.gbif_occurrence_raw",
    "shark_knowledge.silver.wikipedia_pages",
    "shark_knowledge.silver.gbif_taxonomy",
    "shark_knowledge.silver.gbif_occurrences",
    "shark_knowledge.silver.rejected_records",
    "shark_knowledge.gold.species",
    "shark_knowledge.gold.species_chunks",
]

for t in tables:
    try:
        n = spark.sql(f"SELECT COUNT(*) AS n FROM {t}").collect()[0]["n"]
        print(f"{t:55s} rows={n}")
    except Exception as e:
        print(f"{t:55s} ERROR: {e}")

# Databricks notebook source
# MAGIC %md
# MAGIC ## 2. Gold acceptance checks

# Databricks notebook source
species_count = spark.sql("SELECT COUNT(*) AS n FROM shark_knowledge.gold.species").collect()[0]["n"]
chunk_count = spark.sql("SELECT COUNT(*) AS n FROM shark_knowledge.gold.species_chunks").collect()[0]["n"]

species_with_chunks = spark.sql("""
    SELECT COUNT(DISTINCT species_key) AS n
    FROM shark_knowledge.gold.species_chunks
""").collect()[0]["n"]

print("gold.species rows          =", species_count, "(expected 18)")
print("gold.species_chunks rows   =", chunk_count, "(expected >= 18)")
print("species with >=1 chunk     =", species_with_chunks, "(expected 18)")

assert species_count == 18, "gold.species must have exactly 18 rows"
assert species_with_chunks == 18, "every accepted species must have at least one chunk"
print("PASS: seed dataset acceptance criteria met.")

# Databricks notebook source
# MAGIC %md
# MAGIC ## 3. Rerun convergence (idempotency)

# Databricks notebook source
before_species = spark.sql("SELECT COUNT(*) AS n FROM shark_knowledge.gold.species").collect()[0]["n"]
before_chunks = spark.sql("SELECT COUNT(*) AS n FROM shark_knowledge.gold.species_chunks").collect()[0]["n"]
before_hashes = spark.sql("SELECT COUNT(DISTINCT content_hash) AS n FROM shark_knowledge.gold.species").collect()[0]["n"]

run_pipeline(SEED_SCIENTIFIC_NAMES, batch_id="seed_batch_01")

after_species = spark.sql("SELECT COUNT(*) AS n FROM shark_knowledge.gold.species").collect()[0]["n"]
after_chunks = spark.sql("SELECT COUNT(*) AS n FROM shark_knowledge.gold.species_chunks").collect()[0]["n"]
after_hashes = spark.sql("SELECT COUNT(DISTINCT content_hash) AS n FROM shark_knowledge.gold.species").collect()[0]["n"]

print("gold.species new rows      =", after_species - before_species, "(expected 0)")
print("gold.species_chunks new    =", after_chunks - before_chunks, "(expected 0)")
print("gold content_hash changes  =", after_hashes - before_hashes, "(expected 0)")

assert after_species == before_species
assert after_chunks == before_chunks
assert after_hashes == before_hashes
print("PASS: rerun converged (0 new species, 0 new chunks, 0 hash changes).")
