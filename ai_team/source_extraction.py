"""Extract the structured ``sources`` array from a model response.

This module is intentionally dependency-free: it only needs the standard
library, so it can be imported by adapters and pipeline code without pulling
in third-party HTTP clients.
"""

import json
import re
from typing import Any

_JSON_FENCE_PATTERN = re.compile(
    r"```json\s*(.*?)```",
    re.IGNORECASE | re.DOTALL,
)


def _decode_sources(value: Any) -> list[dict] | None:
    """Return the ``sources`` array from an already-decoded JSON value."""
    if isinstance(value, dict):
        sources = value.get("sources")
    elif isinstance(value, list):
        sources = value
    else:
        return None

    if not isinstance(sources, list):
        return None

    return [item for item in sources if isinstance(item, dict)]


def _extract_candidates(text: str, start_char: str) -> list[list[dict]]:
    """Scan every ``{`` / ``[`` position and keep the decodable payloads."""
    decoder = json.JSONDecoder()
    results = []

    for index, char in enumerate(text):
        if char != start_char:
            continue

        try:
            value, _ = decoder.raw_decode(text[index:])
        except (ValueError, TypeError):
            continue

        result = _decode_sources(value)
        if result is not None:
            results.append(result)

    return results


def extract_sources_from_content(content: str) -> list[dict] | None:
    """Best-effort extraction of the ``sources`` array from a report body.

    Preference order: fenced ``json`` blocks, then bare JSON objects, then
    bare JSON arrays. The last decodable candidate wins, because models tend
    to show an example first and the real payload afterwards. Any failure
    degrades to ``None`` instead of raising.
    """
    try:
        candidates = []
        for block in _JSON_FENCE_PATTERN.findall(content):
            try:
                result = _decode_sources(json.loads(block))
                if result is not None:
                    candidates.append(result)
            except Exception:
                continue
        if candidates:
            return candidates[-1]
        candidates = _extract_candidates(content, "{")
        if candidates:
            return candidates[-1]
        candidates = _extract_candidates(content, "[")
        if candidates:
            return candidates[-1]
        return None
    except Exception:
        return None


def extract_sources_or_empty(content: str) -> list[dict]:
    """Same as :func:`extract_sources_from_content` but never returns None."""
    return extract_sources_from_content(content) or []


__all__ = [
    "extract_sources_from_content",
    "extract_sources_or_empty",
]
