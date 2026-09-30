# Databricks notebook source
# MAGIC %md
# MAGIC # 01 — Run Pipeline (Seed Batch)
# MAGIC
# MAGIC Runs the full medallion pipeline (Bronze -> Silver -> Gold) for the
# MAGIC 18-species seed batch. Re-running this notebook is safe: Bronze appends,
# MAGIC Silver and Gold converge via content-aware MERGE.

# Databricks notebook source
# MAGIC %run ./00_bootstrap

# Databricks notebook source
summary = run_pipeline(SEED_SCIENTIFIC_NAMES, batch_id="seed_batch_01")

# Databricks notebook source
# MAGIC %md
# MAGIC ## Pipeline summary

# Databricks notebook source
import json

print(json.dumps(summary, indent=2, default=str))
