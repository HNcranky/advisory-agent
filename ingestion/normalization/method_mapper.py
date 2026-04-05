# normalization/method_mapper.py
"""
Map raw admission method text to canonical method codes.

School-aware: looks up school-specific methods first,
then falls back to shared methods.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

_METHODS_CACHE: Optional[Dict[str, Any]] = None


def _load_all() -> Dict[str, Any]:
    """Load the full methods dictionary."""
    global _METHODS_CACHE
    if _METHODS_CACHE is None:
        dict_path = (
            Path(__file__).parent / "dictionaries" / "methods.json"
        )
        with open(dict_path, "r", encoding="utf-8") as f:
            _METHODS_CACHE = json.load(f)
    return _METHODS_CACHE


def _load_dict(school_id: str = "") -> dict:
    """
    Build a merged dictionary for a specific school.
    School-specific entries override shared entries with the same key.
    """
    all_data = _load_all()
    shared = all_data.get("_shared", {})
    school = all_data.get(school_id, {}) if school_id else {}

    merged = {}
    merged.update(shared)
    merged.update(school)
    return merged


def map_method(
    raw_method: Optional[str],
    school_id: str = "",
) -> Optional[str]:
    """
    Map raw admission method text to canonical code.

    Args:
        raw_method: Raw admission method string
        school_id: School identifier for school-specific lookup

    Returns:
        Canonical method code or the raw text if no match
    """
    if not raw_method:
        return None

    methods = _load_dict(school_id)
    raw_lower = raw_method.lower().strip()

    # Check each method's aliases
    for method_code, info in methods.items():
        canonical_name = info["canonical_name"]
        aliases = info.get("aliases", [])

        # Exact match
        if raw_lower == canonical_name.lower():
            return method_code

        for alias in aliases:
            if alias.lower() in raw_lower:
                return method_code

    # If raw contains multiple methods, try to identify each
    found_methods = []
    for method_code, info in methods.items():
        aliases = info.get("aliases", [])
        for alias in aliases:
            if alias.lower() in raw_lower:
                if method_code not in found_methods:
                    found_methods.append(method_code)
                break

    if found_methods:
        return "; ".join(found_methods)

    logger.debug(f"No canonical match for method: '{raw_method}'")
    return raw_method
