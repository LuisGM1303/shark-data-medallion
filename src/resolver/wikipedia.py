"""Wikipedia title resolution: DIRECT_TITLE, SEARCH, REDIRECT, or rejection."""

from enum import Enum

import requests


class ResolutionMethod(str, Enum):
    DIRECT_TITLE = "DIRECT_TITLE"
    SEARCH = "SEARCH"
    REDIRECT = "REDIRECT"


class WikipediaResolution:
    def __init__(self, title: str | None = None, page_url: str | None = None, resolved_via: ResolutionMethod | None = None):
        self.title = title
        self.page_url = page_url
        self.resolved_via = resolved_via


def resolve_wikipedia_title(scientific_name: str) -> WikipediaResolution:
    raise NotImplementedError
