# normalization/method_mapper.py
"""
Map raw admission method text to canonical method codes.
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_METHODS_DICT = None


def _load_dict() -> dict:
    global _METHODS_DICT
    if _METHODS_DICT is None:
        dict_path = (
            Path(__file__).parent / "dictionaries" / "methods.json"
        )
        with open(dict_path, "r", encoding="utf-8") as f:
            _METHODS_DICT = json.load(f)
    return _METHODS_DICT


def map_method(raw_method: Optional[str]) -> Optional[str]:
    """
    Map raw admission method text to canonical code.

    Args:
        raw_method: Raw admission method string

    Returns:
        Canonical method code or the raw text if no match
    """
    if not raw_method:
        return None

    methods = _load_dict()
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
    # (e.g. "Đánh giá tư duy (TSA); Xét điểm thi TN THPT")
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
