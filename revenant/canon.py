"""Canonical JSON encoding used for state hashing."""

from __future__ import annotations

import json
import math
import unicodedata
from typing import Any


class CanonError(ValueError):
    """Raised when a value cannot be encoded canonically."""


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def _normalise(obj: Any) -> Any:
    if isinstance(obj, str):
        return _nfc(obj)
    if isinstance(obj, float) and not math.isfinite(obj):
        raise CanonError(f"non-finite float is not allowed: {obj!r}")
    if isinstance(obj, dict):
        return {_nfc(k): _normalise(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalise(v) for v in obj]
    return obj


def canonical_json(obj: Any) -> bytes:
    """Encode ``obj`` as canonical JSON: sorted keys, compact separators, UTF-8."""
    return json.dumps(
        _normalise(obj),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
