"""Silver validation logic per source."""

from enum import Enum


class RejectionReason(str, Enum):
    # Wikipedia
    PAGE_NOT_FOUND = "PAGE_NOT_FOUND"
    AMBIGUOUS_RESOLUTION = "AMBIGUOUS_RESOLUTION"
    EXTRACT_TOO_SHORT = "EXTRACT_TOO_SHORT"
    DISAMBIGUATION_PAGE = "DISAMBIGUATION_PAGE"
    HTTP_ERROR = "HTTP_ERROR"
    MISSING_SECTIONS_TEXT = "MISSING_SECTIONS_TEXT"
    # GBIF Taxonomy
    MATCH_TYPE_NOT_EXACT = "MATCH_TYPE_NOT_EXACT"
    NO_MATCH_RETURNED = "NO_MATCH_RETURNED"
    # GBIF Occurrence
    MISSING_COORDINATES = "MISSING_COORDINATES"
    COORDINATES_OUT_OF_RANGE = "COORDINATES_OUT_OF_RANGE"
    MISSING_GBIF_ID = "MISSING_GBIF_ID"
    INVALID_EVENT_DATE = "INVALID_EVENT_DATE"
    MISSING_BASIS_OF_RECORD = "MISSING_BASIS_OF_RECORD"


def validate_wikipedia(data: dict) -> dict:
    raise NotImplementedError


def validate_gbif_taxonomy(data: dict) -> dict:
    raise NotImplementedError


def validate_gbif_occurrence(data: dict) -> dict:
    raise NotImplementedError
