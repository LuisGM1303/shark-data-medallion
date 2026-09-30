"""Deterministic content hashing (global data convention, SAS v2 section 9.3).

content_hash is a SHA-256 over a canonical representation of business fields.
Operational fields (run_id, validated_at, timestamps) are excluded by the
caller. Canonical serialization uses UTF-8, stable field ordering, stable NULL
representation and deterministic list ordering.
"""

from __future__ import annotations

import hashlib
import json


def _canonical(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    if isinstance(value, dict):
        return {k: _canonical(v) for k, v in sorted(value.items())}
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def content_hash(fields: dict) -> str:
    canonical = _canonical(fields)
    serialized = json.dumps(canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def record_hash(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def rejection_id(source: str, natural_key: str | None, reason: str, record_hash: str) -> str:
    raw = f"{source}|{natural_key}|{reason}|{record_hash}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
