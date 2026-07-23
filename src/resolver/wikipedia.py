from __future__ import annotations

from enum import Enum

import requests

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
WIKIPEDIA_REST = "https://en.wikipedia.org/api/rest_v1"

_HEADERS = {
    "User-Agent": "SharkKnowledgeMedallion/1.0 (educational project; mailto:example@example.com)"
}


class ResolutionMethod(str, Enum):
    DIRECT_TITLE = "DIRECT_TITLE"
    SEARCH = "SEARCH"
    REDIRECT = "REDIRECT"


class WikipediaResolution:
    def __init__(
        self,
        title: str | None = None,
        page_url: str | None = None,
        resolved_via: ResolutionMethod | None = None,
        is_disambiguation: bool = False,
        candidates: list[str] | None = None,
    ):
        self.title = title
        self.page_url = page_url
        self.resolved_via = resolved_via
        self.is_disambiguation = is_disambiguation
        self.candidates = candidates


def _fetch_page_info(title: str) -> dict | None:
    params = {
        "action": "query",
        "titles": title,
        "prop": "info|pageprops",
        "format": "json",
        "redirects": 1,
    }
    resp = requests.get(WIKIPEDIA_API, params=params, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    pages = data.get("query", {}).get("pages", {})
    for page_id, page in pages.items():
        if page_id == "-1":
            return None
        return page
    return None


def resolve_wikipedia_title(scientific_name: str) -> WikipediaResolution:
    direct = _fetch_page_info(scientific_name)
    if direct:
        title = direct.get("title", scientific_name)
        pageprops = direct.get("pageprops", {})
        is_disambig = pageprops.get("disambiguation") is not None
        page_url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
        if is_disambig:
            return WikipediaResolution(
                title=title,
                page_url=page_url,
                resolved_via=ResolutionMethod.DIRECT_TITLE,
                is_disambiguation=True,
            )
        return WikipediaResolution(
            title=title,
            page_url=page_url,
            resolved_via=ResolutionMethod.DIRECT_TITLE,
        )

    search_params = {
        "action": "query",
        "list": "search",
        "srsearch": scientific_name,
        "format": "json",
        "srlimit": 5,
    }
    search_resp = requests.get(WIKIPEDIA_API, params=search_params, headers=_HEADERS, timeout=15)
    search_resp.raise_for_status()
    search_data = search_resp.json()
    search_results = search_data.get("query", {}).get("search", [])

    if not search_results:
        return WikipediaResolution(resolved_via=None)

    candidates = [r["title"] for r in search_results]
    top = search_results[0]
    top_title = top["title"]
    top_info = _fetch_page_info(top_title)
    if not top_info:
        return WikipediaResolution(resolved_via=None, candidates=candidates)

    pageprops = top_info.get("pageprops", {})
    is_disambig = pageprops.get("disambiguation") is not None
    page_url = f"https://en.wikipedia.org/wiki/{top_title.replace(' ', '_')}"

    if is_disambig and len(search_results) > 1:
        second = search_results[1]
        second_info = _fetch_page_info(second["title"])
        if second_info:
            sprops = second_info.get("pageprops", {})
            if sprops.get("disambiguation") is None:
                top_title = second["title"]
                page_url = f"https://en.wikipedia.org/wiki/{top_title.replace(' ', '_')}"
                return WikipediaResolution(
                    title=top_title,
                    page_url=page_url,
                    resolved_via=ResolutionMethod.SEARCH,
                )

    if is_disambig:
        return WikipediaResolution(
            title=top_title,
            page_url=page_url,
            resolved_via=ResolutionMethod.SEARCH,
            is_disambiguation=True,
            candidates=candidates,
        )

    return WikipediaResolution(
        title=top_title,
        page_url=page_url,
        resolved_via=ResolutionMethod.SEARCH,
    )
