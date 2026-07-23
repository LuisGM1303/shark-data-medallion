from __future__ import annotations

import os
from datetime import datetime, timezone

import duckdb


class Warehouse:
    def __init__(self, db_path: str = "data/warehouse.duckdb"):
        self.db_path = db_path
        self._conn: duckdb.DuckDBPyConnection | None = None

    def connect(self) -> duckdb.DuckDBPyConnection:
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        if self._conn is None:
            self._conn = duckdb.connect(self.db_path)
        return self._conn

    def initialize_schema(self) -> None:
        conn = self.connect()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS silver_wikipedia (
                species_key VARCHAR PRIMARY KEY,
                title VARCHAR,
                resolved_via VARCHAR,
                extract VARCHAR,
                sections_text VARCHAR,
                page_url VARCHAR,
                is_disambiguation BOOLEAN
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS silver_gbif_taxonomy (
                species_key VARCHAR PRIMARY KEY,
                usage_key INTEGER,
                scientific_name VARCHAR,
                canonical_name VARCHAR,
                rank VARCHAR,
                match_type VARCHAR,
                confidence INTEGER,
                kingdom VARCHAR,
                phylum VARCHAR,
                class_name VARCHAR
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS silver_gbif_occurrences (
                gbif_id BIGINT PRIMARY KEY,
                species_key VARCHAR,
                decimal_latitude DOUBLE,
                decimal_longitude DOUBLE,
                country VARCHAR,
                event_date TIMESTAMP,
                basis_of_record VARCHAR,
                iucn_red_list_category VARCHAR,
                coordinate_uncertainty_m DOUBLE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS species_merged (
                species_key VARCHAR PRIMARY KEY,
                wikipedia_title VARCHAR,
                extract VARCHAR,
                sections_text VARCHAR,
                kingdom VARCHAR,
                phylum VARCHAR,
                class_name VARCHAR,
                rank VARCHAR,
                taxonomy_status VARCHAR,
                n_occurrences_validas INTEGER,
                paises VARCHAR[],
                anio_min INTEGER,
                anio_max INTEGER,
                iucn_red_list_category VARCHAR,
                augmentation_status VARCHAR,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS species_catalog (
                species_key VARCHAR PRIMARY KEY,
                scientific_name VARCHAR,
                wikipedia_title VARCHAR,
                first_seen_batch_id VARCHAR,
                first_processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                origin VARCHAR
            )
        """)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _count(self, table: str) -> int:
        row = self.connect().execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return row[0] if row else 0

    def _upsert(self, table: str, pk_col: str, columns: list[str], placeholders: list[str], conflict_set: list[str], records: list[dict]) -> dict:
        if not records:
            return {"tabla": table, "filas_antes": self._count(table), "filas_despues": self._count(table), "filas_nuevas": 0, "filas_actualizadas": 0}
        conn = self.connect()
        antes = self._count(table)
        nuevas = 0
        actualizadas = 0
        for rec in records:
            existing = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {pk_col} = ?", [rec[pk_col]]).fetchone()[0]
            cols_str = ", ".join(columns)
            phs_str = ", ".join(placeholders)
            updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in conflict_set)
            values = [rec.get(c) for c in columns]
            conn.execute(f"""
                INSERT INTO {table} ({cols_str}) VALUES ({phs_str})
                ON CONFLICT ({pk_col}) DO UPDATE SET {updates}
            """, values)
            if existing == 0:
                nuevas += 1
            else:
                actualizadas += 1
        despues = self._count(table)
        return {"tabla": table, "filas_antes": antes, "filas_despues": despues, "filas_nuevas": nuevas, "filas_actualizadas": actualizadas}

    def upsert_wikipedia(self, records: list[dict]) -> dict:
        cols = ["species_key", "title", "resolved_via", "extract", "sections_text", "page_url", "is_disambiguation"]
        return self._upsert("silver_wikipedia", "species_key", cols, ["?"] * len(cols), [c for c in cols if c != "species_key"], records)

    def upsert_gbif_taxonomy(self, records: list[dict]) -> dict:
        cols = ["species_key", "usage_key", "scientific_name", "canonical_name", "rank", "match_type", "confidence", "kingdom", "phylum", "class_name"]
        return self._upsert("silver_gbif_taxonomy", "species_key", cols, ["?"] * len(cols), [c for c in cols if c != "species_key"], records)

    def upsert_gbif_occurrences(self, records: list[dict]) -> dict:
        cols = ["gbif_id", "species_key", "decimal_latitude", "decimal_longitude", "country", "event_date", "basis_of_record", "iucn_red_list_category", "coordinate_uncertainty_m"]
        return self._upsert("silver_gbif_occurrences", "gbif_id", cols, ["?"] * len(cols), [c for c in cols if c != "gbif_id"], records)

    def upsert_species_merged(self, records: list[dict]) -> dict:
        if not records:
            table = "species_merged"
            return {"tabla": table, "filas_antes": self._count(table), "filas_despues": self._count(table), "filas_nuevas": 0, "filas_actualizadas": 0}
        conn = self.connect()
        table = "species_merged"
        antes = self._count(table)
        nuevas = 0
        actualizadas = 0
        for rec in records:
            existing = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE species_key = ?", [rec["species_key"]]).fetchone()[0]
            conn.execute(f"""
                INSERT INTO {table} (species_key, wikipedia_title, extract, sections_text, kingdom, phylum, class_name, rank, taxonomy_status, n_occurrences_validas, paises, anio_min, anio_max, iucn_red_list_category, augmentation_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (species_key) DO UPDATE SET
                    wikipedia_title = EXCLUDED.wikipedia_title,
                    extract = EXCLUDED.extract,
                    sections_text = EXCLUDED.sections_text,
                    kingdom = EXCLUDED.kingdom,
                    phylum = EXCLUDED.phylum,
                    class_name = EXCLUDED.class_name,
                    rank = EXCLUDED.rank,
                    taxonomy_status = EXCLUDED.taxonomy_status,
                    n_occurrences_validas = EXCLUDED.n_occurrences_validas,
                    paises = EXCLUDED.paises,
                    anio_min = EXCLUDED.anio_min,
                    anio_max = EXCLUDED.anio_max,
                    iucn_red_list_category = EXCLUDED.iucn_red_list_category,
                    augmentation_status = EXCLUDED.augmentation_status
            """, [rec["species_key"], rec.get("wikipedia_title"), rec.get("extract"), rec.get("sections_text"), rec.get("kingdom"), rec.get("phylum"), rec.get("class_name"), rec.get("rank"), rec.get("taxonomy_status"), rec.get("n_occurrences_validas", 0), rec.get("paises", []), rec.get("anio_min"), rec.get("anio_max"), rec.get("iucn_red_list_category"), rec.get("augmentation_status")])
            if existing == 0:
                nuevas += 1
            else:
                actualizadas += 1
        despues = self._count(table)
        return {"tabla": table, "filas_antes": antes, "filas_despues": despues, "filas_nuevas": nuevas, "filas_actualizadas": actualizadas}

    def upsert_species_catalog(self, records: list[dict], batch_id: str) -> dict:
        if not records:
            table = "species_catalog"
            return {"tabla": table, "filas_antes": self._count(table), "filas_despues": self._count(table), "filas_nuevas": 0, "filas_actualizadas": 0}
        conn = self.connect()
        table = "species_catalog"
        antes = self._count(table)
        nuevas = 0
        actualizadas = 0
        for rec in records:
            existing = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE species_key = ?", [rec["species_key"]]).fetchone()[0]
            conn.execute(f"""
                INSERT INTO {table} (species_key, scientific_name, wikipedia_title, first_seen_batch_id, last_processed_at, origin)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (species_key) DO UPDATE SET
                    wikipedia_title = EXCLUDED.wikipedia_title,
                    last_processed_at = now()
            """, [rec["species_key"], rec.get("scientific_name", ""), rec.get("wikipedia_title", ""), batch_id, self._now(), rec.get("origin", "AD_HOC")])
            if existing == 0:
                nuevas += 1
            else:
                actualizadas += 1
        despues = self._count(table)
        return {"tabla": table, "filas_antes": antes, "filas_despues": despues, "filas_nuevas": nuevas, "filas_actualizadas": actualizadas}

    def get_evidence(self) -> list[dict]:
        tables = ["silver_wikipedia", "silver_gbif_taxonomy", "silver_gbif_occurrences", "species_merged", "species_catalog"]
        conn = self.connect()
        evidence = []
        for tbl in tables:
            count = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            evidence.append({"tabla": tbl, "count": count})
        return evidence
