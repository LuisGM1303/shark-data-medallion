"""Warehouse layer: DuckDB UPSERT operations."""

import duckdb


class Warehouse:
    def __init__(self, db_path: str = "data/warehouse.duckdb"):
        self.db_path = db_path

    def connect(self) -> duckdb.DuckDBPyConnection:
        raise NotImplementedError

    def initialize_schema(self) -> None:
        raise NotImplementedError

    def upsert_wikipedia(self, records: list[dict]) -> dict:
        raise NotImplementedError

    def upsert_gbif_taxonomy(self, records: list[dict]) -> dict:
        raise NotImplementedError

    def upsert_gbif_occurrences(self, records: list[dict]) -> dict:
        raise NotImplementedError

    def upsert_species_merged(self, records: list[dict]) -> dict:
        raise NotImplementedError

    def upsert_species_catalog(self, records: list[dict], batch_id: str) -> dict:
        raise NotImplementedError

    def get_evidence(self) -> list[dict]:
        raise NotImplementedError
