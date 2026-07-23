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


class ResolutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PAGE_NOT_FOUND = "PAGE_NOT_FOUND"
    AMBIGUOUS_RESOLUTION = "AMBIGUOUS_RESOLUTION"
    DISAMBIGUATION_PAGE = "DISAMBIGUATION_PAGE"
    NO_MATCH = "NO_MATCH"


class WikipediaResolution:
    def __init__(
        self,
        title: str | None = None,
        page_url: str | None = None,
        resolved_via: ResolutionMethod | None = None,
        is_disambiguation: bool = False,
        candidates: list[str] | None = None,
        status: ResolutionStatus = ResolutionStatus.SUCCESS,
    ):
        self.title = title
        self.page_url = page_url
        self.resolved_via = resolved_via
        self.is_disambiguation = is_disambiguation
        self.candidates = candidates
        self.status = status


def _fetch_page_info(title: str) -> tuple[dict | None, bool]:
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
    was_redirected = False
    redirects = data.get("query", {}).get("redirects", [])
    if redirects:
        was_redirected = True
    for page_id, page in pages.items():
        if page_id == "-1":
            return None, was_redirected
        return page, was_redirected
    return None, was_redirected


def resolve_wikipedia_title(title_or_name: str) -> WikipediaResolution:
    page_info, was_redirected = _fetch_page_info(title_or_name)
    if page_info:
        title = page_info.get("title", title_or_name)
        pageprops = page_info.get("pageprops", {})
        is_disambig = pageprops.get("disambiguation") is not None
        page_url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"

        if is_disambig:
            return WikipediaResolution(
                title=title,
                page_url=page_url,
                resolved_via=ResolutionMethod.DIRECT_TITLE if not was_redirected else ResolutionMethod.REDIRECT,
                is_disambiguation=True,
                status=ResolutionStatus.DISAMBIGUATION_PAGE,
            )

        if was_redirected:
            return WikipediaResolution(
                title=title,
                page_url=page_url,
                resolved_via=ResolutionMethod.REDIRECT,
            )

        return WikipediaResolution(
            title=title,
            page_url=page_url,
            resolved_via=ResolutionMethod.DIRECT_TITLE,
        )

    search_params = {
        "action": "query",
        "list": "search",
        "srsearch": title_or_name,
        "format": "json",
        "srlimit": 5,
    }
    search_resp = requests.get(WIKIPEDIA_API, params=search_params, headers=_HEADERS, timeout=15)
    search_resp.raise_for_status()
    search_data = search_resp.json()
    search_results = search_data.get("query", {}).get("search", [])

    if not search_results:
        return WikipediaResolution(
            status=ResolutionStatus.PAGE_NOT_FOUND,
        )

    candidates = [r["title"] for r in search_results]
    top = search_results[0]
    top_title = top["title"]
    top_info, _ = _fetch_page_info(top_title)
    if not top_info:
        return WikipediaResolution(
            status=ResolutionStatus.PAGE_NOT_FOUND,
            candidates=candidates,
        )

    pageprops = top_info.get("pageprops", {})
    is_disambig = pageprops.get("disambiguation") is not None
    page_url = f"https://en.wikipedia.org/wiki/{top_title.replace(' ', '_')}"

    if is_disambig and len(search_results) > 1:
        second = search_results[1]
        second_info, _ = _fetch_page_info(second["title"])
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
            status=ResolutionStatus.DISAMBIGUATION_PAGE,
        )

    if len(search_results) >= 2:
        second = search_results[1]
        top_snippet = top.get("snippet", "")
        second_snippet = second.get("snippet", "")
        title_lower = title_or_name.lower()
        top_has_name = title_lower in top_snippet.lower() or title_lower in top_title.lower()
        second_has_name = title_lower in second_snippet.lower() or title_lower in second["title"].lower()
        if top_has_name and second_has_name:
            return WikipediaResolution(
                status=ResolutionStatus.AMBIGUOUS_RESOLUTION,
                candidates=candidates,
            )

    return WikipediaResolution(
        title=top_title,
        page_url=page_url,
        resolved_via=ResolutionMethod.SEARCH,
    )
