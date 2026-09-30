"""Delta persistence for the Databricks-centric medallion architecture.

Centralizes all Delta write behavior (SAS v2 section 16.1):

- Bronze: append-only raw tables.
- Silver: current-state tables with MERGE by natural key + content_hash.
- Gold: canonical Species and SpeciesChunks with MERGE by natural key.

The module stays simple: no repositories, ports/adapters or services.
"""

from __future__ import annotations

from pyspark.sql import SparkSession
from pyspark.sql.types import (
    ArrayType,
    BooleanType,
    DoubleType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from src.config.seed_species import (
    BRONZE_GBIF_OCCURRENCE,
    BRONZE_GBIF_TAXONOMY,
    BRONZE_WIKIPEDIA,
    CATALOG,
    GOLD_SPECIES,
    GOLD_SPECIES_CHUNKS,
    SCHEMA_BRONZE,
    SCHEMA_GOLD,
    SCHEMA_SILVER,
    SILVER_GBIF_OCCURRENCES,
    SILVER_GBIF_TAXONOMY,
    SILVER_REJECTED,
    SILVER_WIKIPEDIA,
)

_spark: SparkSession | None = None


def set_spark(spark: SparkSession) -> None:
    global _spark
    _spark = spark


def _get_spark() -> SparkSession:
    if _spark is None:
        raise RuntimeError(
            "Spark session not set. Call set_spark(spark) or pass spark= to run_pipeline()."
        )
    return _spark


# ---------------------------------------------------------------------------
# Schemas (must match the DDL below exactly).
# ---------------------------------------------------------------------------

BRONZE_SCHEMA = StructType([
    StructField("ingestion_id", StringType(), False),
    StructField("run_id", StringType(), False),
    StructField("batch_id", StringType(), False),
    StructField("species_key", StringType(), False),
    StructField("scientific_name", StringType(), False),
    StructField("raw_payload", StringType(), False),
    StructField("ingested_at", TimestampType(), False),
])

WIKIPEDIA_SCHEMA = StructType([
    StructField("species_key", StringType(), False),
    StructField("title", StringType(), False),
    StructField("resolved_via", StringType(), False),
    StructField("extract", StringType(), False),
    StructField("sections_text", StringType(), False),
    StructField("page_url", StringType(), False),
    StructField("is_disambiguation", BooleanType(), False),
    StructField("source_ingestion_id", StringType(), False),
    StructField("content_hash", StringType(), False),
    StructField("validated_at", TimestampType(), False),
])

TAXONOMY_SCHEMA = StructType([
    StructField("species_key", StringType(), False),
    StructField("usage_key", LongType(), False),
    StructField("scientific_name", StringType(), False),
    StructField("canonical_name", StringType(), False),
    StructField("rank", StringType(), False),
    StructField("match_type", StringType(), False),
    StructField("confidence", IntegerType(), False),
    StructField("kingdom", StringType(), True),
    StructField("phylum", StringType(), True),
    StructField("class_name", StringType(), True),
    StructField("source_ingestion_id", StringType(), False),
    StructField("content_hash", StringType(), False),
    StructField("validated_at", TimestampType(), False),
])

OCCURRENCE_SCHEMA = StructType([
    StructField("gbif_id", LongType(), False),
    StructField("species_key", StringType(), False),
    StructField("decimal_latitude", DoubleType(), False),
    StructField("decimal_longitude", DoubleType(), False),
    StructField("country", StringType(), True),
    StructField("event_date", TimestampType(), True),
    StructField("basis_of_record", StringType(), False),
    StructField("iucn_red_list_category", StringType(), True),
    StructField("coordinate_uncertainty_m", DoubleType(), True),
    StructField("source_ingestion_id", StringType(), False),
    StructField("content_hash", StringType(), False),
    StructField("validated_at", TimestampType(), False),
])

REJECTED_SCHEMA = StructType([
    StructField("rejection_id", StringType(), False),
    StructField("run_id", StringType(), False),
    StructField("batch_id", StringType(), False),
    StructField("source", StringType(), False),
    StructField("species_key", StringType(), True),
    StructField("natural_key", StringType(), True),
    StructField("rejection_reason", StringType(), False),
    StructField("rejection_detail", StringType(), True),
    StructField("record_payload", StringType(), False),
    StructField("record_hash", StringType(), False),
    StructField("source_ingestion_id", StringType(), True),
    StructField("rejected_at", TimestampType(), False),
])

SPECIES_SCHEMA = StructType([
    StructField("species_key", StringType(), False),
    StructField("scientific_name", StringType(), False),
    StructField("wikipedia_title", StringType(), False),
    StructField("document_uri", StringType(), False),
    StructField("identity", StringType(), True),
    StructField("taxonomy", StringType(), True),
    StructField("morphology", StringType(), True),
    StructField("distribution", StringType(), True),
    StructField("habitat", StringType(), True),
    StructField("behavior", StringType(), True),
    StructField("diet", StringType(), True),
    StructField("reproduction", StringType(), True),
    StructField("conservation", StringType(), True),
    StructField("human_interaction", StringType(), True),
    StructField("references", StringType(), True),
    StructField("multimedia", StringType(), True),
    StructField("document_text", StringType(), False),
    StructField("kingdom", StringType(), True),
    StructField("phylum", StringType(), True),
    StructField("class_name", StringType(), True),
    StructField("rank", StringType(), True),
    StructField("taxonomy_status", StringType(), False),
    StructField("iucn_red_list_category", StringType(), True),
    StructField("countries", ArrayType(StringType()), False),
    StructField("year_min", IntegerType(), True),
    StructField("year_max", IntegerType(), True),
    StructField("n_valid_occurrences", LongType(), False),
    StructField("augmentation_status", StringType(), False),
    StructField("origin", StringType(), False),
    StructField("first_processed_at", TimestampType(), False),
    StructField("last_content_change_at", TimestampType(), False),
    StructField("content_hash", StringType(), False),
])

CHUNK_SCHEMA = StructType([
    StructField("chunk_id", StringType(), False),
    StructField("species_key", StringType(), False),
    StructField("section", StringType(), False),
    StructField("chunk_ordinal", IntegerType(), False),
    StructField("text", StringType(), False),
    StructField("scientific_name", StringType(), False),
    StructField("wikipedia_title", StringType(), False),
    StructField("document_uri", StringType(), False),
    StructField("kingdom", StringType(), True),
    StructField("phylum", StringType(), True),
    StructField("class_name", StringType(), True),
    StructField("rank", StringType(), True),
    StructField("taxonomy_status", StringType(), False),
    StructField("iucn_red_list_category", StringType(), True),
    StructField("countries", ArrayType(StringType()), False),
    StructField("year_min", IntegerType(), True),
    StructField("year_max", IntegerType(), True),
    StructField("n_valid_occurrences", LongType(), False),
    StructField("augmentation_status", StringType(), False),
    StructField("parent_content_hash", StringType(), False),
    StructField("content_hash", StringType(), False),
    StructField("last_content_change_at", TimestampType(), False),
])


# ---------------------------------------------------------------------------
# Schema / table creation.
# ---------------------------------------------------------------------------

def ensure_schema(spark: SparkSession | None = None) -> None:
    s = spark or _get_spark()

    s.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
    s.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA_BRONZE}")
    s.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA_SILVER}")
    s.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA_GOLD}")

    s.sql(f"""
        CREATE TABLE IF NOT EXISTS {BRONZE_WIKIPEDIA} (
            ingestion_id STRING NOT NULL,
            run_id STRING NOT NULL,
            batch_id STRING NOT NULL,
            species_key STRING NOT NULL,
            scientific_name STRING NOT NULL,
            raw_payload STRING NOT NULL,
            ingested_at TIMESTAMP NOT NULL
        )
    """)
    s.sql(f"""
        CREATE TABLE IF NOT EXISTS {BRONZE_GBIF_TAXONOMY} (
            ingestion_id STRING NOT NULL,
            run_id STRING NOT NULL,
            batch_id STRING NOT NULL,
            species_key STRING NOT NULL,
            scientific_name STRING NOT NULL,
            raw_payload STRING NOT NULL,
            ingested_at TIMESTAMP NOT NULL
        )
    """)
    s.sql(f"""
        CREATE TABLE IF NOT EXISTS {BRONZE_GBIF_OCCURRENCE} (
            ingestion_id STRING NOT NULL,
            run_id STRING NOT NULL,
            batch_id STRING NOT NULL,
            species_key STRING NOT NULL,
            scientific_name STRING NOT NULL,
            raw_payload STRING NOT NULL,
            ingested_at TIMESTAMP NOT NULL
        )
    """)

    s.sql(f"""
        CREATE TABLE IF NOT EXISTS {SILVER_WIKIPEDIA} (
            species_key STRING NOT NULL,
            title STRING NOT NULL,
            resolved_via STRING NOT NULL,
            extract STRING NOT NULL,
            sections_text STRING NOT NULL,
            page_url STRING NOT NULL,
            is_disambiguation BOOLEAN NOT NULL,
            source_ingestion_id STRING NOT NULL,
            content_hash STRING NOT NULL,
            validated_at TIMESTAMP NOT NULL
        )
    """)
    s.sql(f"""
        CREATE TABLE IF NOT EXISTS {SILVER_GBIF_TAXONOMY} (
            species_key STRING NOT NULL,
            usage_key BIGINT NOT NULL,
            scientific_name STRING NOT NULL,
            canonical_name STRING NOT NULL,
            rank STRING NOT NULL,
            match_type STRING NOT NULL,
            confidence INT NOT NULL,
            kingdom STRING,
            phylum STRING,
            class_name STRING,
            source_ingestion_id STRING NOT NULL,
            content_hash STRING NOT NULL,
            validated_at TIMESTAMP NOT NULL
        )
    """)
    s.sql(f"""
        CREATE TABLE IF NOT EXISTS {SILVER_GBIF_OCCURRENCES} (
            gbif_id BIGINT NOT NULL,
            species_key STRING NOT NULL,
            decimal_latitude DOUBLE NOT NULL,
            decimal_longitude DOUBLE NOT NULL,
            country STRING,
            event_date TIMESTAMP,
            basis_of_record STRING NOT NULL,
            iucn_red_list_category STRING,
            coordinate_uncertainty_m DOUBLE,
            source_ingestion_id STRING NOT NULL,
            content_hash STRING NOT NULL,
            validated_at TIMESTAMP NOT NULL
        )
    """)
    s.sql(f"""
        CREATE TABLE IF NOT EXISTS {SILVER_REJECTED} (
            rejection_id STRING NOT NULL,
            run_id STRING NOT NULL,
            batch_id STRING NOT NULL,
            source STRING NOT NULL,
            species_key STRING,
            natural_key STRING,
            rejection_reason STRING NOT NULL,
            rejection_detail STRING,
            record_payload STRING NOT NULL,
            record_hash STRING NOT NULL,
            source_ingestion_id STRING,
            rejected_at TIMESTAMP NOT NULL
        )
    """)

    s.sql(f"""
        CREATE TABLE IF NOT EXISTS {GOLD_SPECIES} (
            species_key STRING NOT NULL,
            scientific_name STRING NOT NULL,
            wikipedia_title STRING NOT NULL,
            document_uri STRING NOT NULL,
            identity STRING,
            taxonomy STRING,
            morphology STRING,
            distribution STRING,
            habitat STRING,
            behavior STRING,
            diet STRING,
            reproduction STRING,
            conservation STRING,
            human_interaction STRING,
            references STRING,
            multimedia STRING,
            document_text STRING NOT NULL,
            kingdom STRING,
            phylum STRING,
            class_name STRING,
            rank STRING,
            taxonomy_status STRING NOT NULL,
            iucn_red_list_category STRING,
            countries ARRAY<STRING> NOT NULL,
            year_min INT,
            year_max INT,
            n_valid_occurrences BIGINT NOT NULL,
            augmentation_status STRING NOT NULL,
            origin STRING NOT NULL,
            first_processed_at TIMESTAMP NOT NULL,
            last_content_change_at TIMESTAMP NOT NULL,
            content_hash STRING NOT NULL
        )
    """)
    s.sql(f"""
        CREATE TABLE IF NOT EXISTS {GOLD_SPECIES_CHUNKS} (
            chunk_id STRING NOT NULL,
            species_key STRING NOT NULL,
            section STRING NOT NULL,
            chunk_ordinal INT NOT NULL,
            text STRING NOT NULL,
            scientific_name STRING NOT NULL,
            wikipedia_title STRING NOT NULL,
            document_uri STRING NOT NULL,
            kingdom STRING,
            phylum STRING,
            class_name STRING,
            rank STRING,
            taxonomy_status STRING NOT NULL,
            iucn_red_list_category STRING,
            countries ARRAY<STRING> NOT NULL,
            year_min INT,
            year_max INT,
            n_valid_occurrences BIGINT NOT NULL,
            augmentation_status STRING NOT NULL,
            parent_content_hash STRING NOT NULL,
            content_hash STRING NOT NULL,
            last_content_change_at TIMESTAMP NOT NULL
        ) TBLPROPERTIES ('delta.enableRowTracking' = 'true')
    """)


# ---------------------------------------------------------------------------
# Bronze: append-only.
# ---------------------------------------------------------------------------

def _append(spark: SparkSession, table: str, rows: list[dict]) -> None:
    if not rows:
        return
    df = spark.createDataFrame(rows, BRONZE_SCHEMA)
    df.write.mode("append").saveAsTable(table)


def append_wikipedia_bronze(spark: SparkSession, rows: list[dict]) -> None:
    _append(spark, BRONZE_WIKIPEDIA, rows)


def append_gbif_taxonomy_bronze(spark: SparkSession, rows: list[dict]) -> None:
    _append(spark, BRONZE_GBIF_TAXONOMY, rows)


def append_gbif_occurrence_bronze(spark: SparkSession, rows: list[dict]) -> None:
    _append(spark, BRONZE_GBIF_OCCURRENCE, rows)


# ---------------------------------------------------------------------------
# Silver + Gold: MERGE by natural key with content_hash update condition.
# ---------------------------------------------------------------------------

def _merge_with_hash(spark: SparkSession, table: str, rows: list[dict],
                     schema: StructType, pk_col: str) -> None:
    if not rows:
        return
    df = spark.createDataFrame(rows, schema)
    df.createOrReplaceTempView("_updates")
    spark.sql(f"""
        MERGE INTO {table} AS t
        USING _updates AS s
        ON t.{pk_col} = s.{pk_col}
        WHEN MATCHED AND t.content_hash <> s.content_hash THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)


def merge_wikipedia_silver(spark: SparkSession, rows: list[dict]) -> None:
    _merge_with_hash(spark, SILVER_WIKIPEDIA, rows, WIKIPEDIA_SCHEMA, "species_key")


def merge_gbif_taxonomy_silver(spark: SparkSession, rows: list[dict]) -> None:
    _merge_with_hash(spark, SILVER_GBIF_TAXONOMY, rows, TAXONOMY_SCHEMA, "species_key")


def merge_gbif_occurrences_silver(spark: SparkSession, rows: list[dict]) -> None:
    _merge_with_hash(spark, SILVER_GBIF_OCCURRENCES, rows, OCCURRENCE_SCHEMA, "gbif_id")


def merge_rejected_records(spark: SparkSession, rows: list[dict]) -> None:
    if not rows:
        return
    df = spark.createDataFrame(rows, REJECTED_SCHEMA)
    df.createOrReplaceTempView("_updates")
    spark.sql(f"""
        MERGE INTO {SILVER_REJECTED} AS t
        USING _updates AS s
        ON t.rejection_id = s.rejection_id
        WHEN NOT MATCHED THEN INSERT *
    """)


def merge_species(spark: SparkSession, rows: list[dict]) -> None:
    _merge_with_hash(spark, GOLD_SPECIES, rows, SPECIES_SCHEMA, "species_key")


def merge_species_chunks(spark: SparkSession, rows: list[dict]) -> None:
    _merge_with_hash(spark, GOLD_SPECIES_CHUNKS, rows, CHUNK_SCHEMA, "chunk_id")
