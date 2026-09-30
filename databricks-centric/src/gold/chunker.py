"""Gold chunking: canonical Species construction + semantic section-first chunks.

Preserved from v1 with one v2 evolution: a canonical section that is too large
is split into N deterministic subchunks (bounded by MAX_CHUNK_BYTES) instead of
always producing exactly one chunk per section.
"""

from __future__ import annotations

import re

from src.gold.models import CANONICAL_SECTIONS, SECTION_ATTR

MAX_CHUNK_BYTES = 24_000

_SECTION_KEYWORDS: dict[str, list[str]] = {
    "Identity": ["identity"],
    "Taxonomy": ["taxonomy", "classification"],
    "Morphology": ["morphology", "description", "anatomy", "appearance"],
    "Distribution": ["distribution", "range", "geographic"],
    "Habitat": ["habitat"],
    "Behavior": ["behavior", "behaviour"],
    "Diet": ["diet", "feeding", "food", "prey", "foraging"],
    "Reproduction": ["reproduction", "breeding", "mating", "life cycle"],
    "Conservation": ["conservation", "threats", "endangered", "status", "population"],
    "Human Interaction": ["human interaction", "shark attack", "human"],
    "References": ["references", "citations", "further reading", "external links"],
    "Multimedia": ["multimedia", "gallery", "media"],
}


def _match_section(section_name: str) -> str | None:
    sl = section_name.lower().strip()
    for canonical, keywords in _SECTION_KEYWORDS.items():
        for kw in keywords:
            if kw in sl:
                return canonical
    return None


def build_species_from_merged(merged: dict) -> dict:
    species_key = merged.get("species_key", "")
    sciname = merged.get("wikipedia_title", "")
    sections_text = merged.get("sections_text", "")

    sections: dict[str, str | None] = {s: None for s in CANONICAL_SECTIONS}
    sections["Identity"] = f"Species: {sciname} ({species_key})"

    tax_status = merged.get("taxonomy_status", "UNMATCHED")
    if tax_status == "MATCHED":
        parts = []
        for k in ["kingdom", "phylum", "class_name", "rank"]:
            v = merged.get(k)
            if v:
                parts.append(f"{k}: {v}")
        sections["Taxonomy"] = "; ".join(parts) if parts else None

    section_pattern = re.compile(r"^==+\s*(.+?)\s*==+", re.MULTILINE)
    current_section = None
    current_content: list[str] = []
    section_map: dict[str, list[str]] = {}

    for line in sections_text.split("\n"):
        m = section_pattern.match(line)
        if m:
            if current_section and current_content:
                sec_map_key = _match_section(current_section.strip())
                if sec_map_key:
                    section_map.setdefault(sec_map_key, []).append("\n".join(current_content).strip())
            current_section = m.group(1)
            current_content = []
        elif current_section:
            current_content.append(line)

    if current_section and current_content:
        sec_map_key = _match_section(current_section.strip())
        if sec_map_key:
            section_map.setdefault(sec_map_key, []).append("\n".join(current_content).strip())

    for sec in CANONICAL_SECTIONS:
        if sec == "Identity":
            continue
        if sec == "Taxonomy" and sections["Taxonomy"]:
            continue
        if sec in section_map:
            content = "\n".join(section_map[sec]).strip()
            if content:
                sections[sec] = content

    species_dict: dict = {"species_key": species_key}
    for canonical, attr in SECTION_ATTR.items():
        species_dict[attr] = sections.get(canonical)

    return species_dict


def build_document_text(species_dict: dict) -> str:
    parts = []
    for canonical in CANONICAL_SECTIONS:
        content = species_dict.get(SECTION_ATTR[canonical])
        if content:
            parts.append(content)
    return "\n\n".join(parts)


def _split_text(text: str, max_bytes: int) -> list[str]:
    if len(text.encode("utf-8")) <= max_bytes:
        return [text]

    words = text.split()
    chunks: list[str] = []
    current: list[str] = []
    current_bytes = 0

    for word in words:
        word_bytes = len(word.encode("utf-8"))
        sep = 1 if current else 0
        if current and current_bytes + sep + word_bytes > max_bytes:
            chunks.append(" ".join(current))
            current = [word]
            current_bytes = word_bytes
        else:
            current.append(word)
            current_bytes += sep + word_bytes

    if current:
        chunks.append(" ".join(current))

    return chunks


def chunk_species(
    species_dict: dict,
    merged: dict,
    scientific_name: str,
    page_url: str,
) -> list[dict]:
    species_key = species_dict.get("species_key", "")
    chunks: list[dict] = []

    for canonical in CANONICAL_SECTIONS:
        attr = SECTION_ATTR[canonical]
        content = species_dict.get(attr)
        if not content or not isinstance(content, str) or not content.strip():
            continue

        parts = _split_text(content.strip(), MAX_CHUNK_BYTES)
        for i, part in enumerate(parts, start=1):
            chunks.append({
                "chunk_id": f"{species_key}__{canonical}__{i:03d}",
                "species_key": species_key,
                "section": canonical,
                "chunk_ordinal": i,
                "text": part,
                "scientific_name": scientific_name,
                "wikipedia_title": merged.get("wikipedia_title", ""),
                "document_uri": page_url,
                "kingdom": merged.get("kingdom"),
                "phylum": merged.get("phylum"),
                "class_name": merged.get("class_name"),
                "rank": merged.get("rank"),
                "taxonomy_status": merged.get("taxonomy_status", "UNMATCHED"),
                "iucn_red_list_category": merged.get("iucn_red_list_category"),
                "countries": merged.get("paises", []),
                "year_min": merged.get("anio_min"),
                "year_max": merged.get("anio_max"),
                "n_valid_occurrences": merged.get("n_occurrences_validas", 0),
                "augmentation_status": merged.get("augmentation_status", "GBIF_AUGMENTATION_EMPTY"),
            })

    return chunks
