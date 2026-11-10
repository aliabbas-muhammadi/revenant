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


def _key_path(path: str, key: str) -> str:
    return f"{path}.{key}"


def _normalise(obj: Any, path: str) -> Any:
    if obj is None or isinstance(obj, bool | int):
        return obj
    if isinstance(obj, str):
        return _nfc(obj)
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise CanonError(f"non-finite float {obj!r} at {path}")
        return obj
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for key, value in obj.items():
            if not isinstance(key, str):
                raise CanonError(f"non-string key of type {type(key).__name__} at {path}")
            out[_nfc(key)] = _normalise(value, _key_path(path, key))
        return out
    if isinstance(obj, list | tuple):
        return [_normalise(v, f"{path}[{i}]") for i, v in enumerate(obj)]
    raise CanonError(f"unsupported type {type(obj).__name__} at {path}")


def canonical_json(obj: Any) -> bytes:
    """Encode ``obj`` as canonical JSON: sorted keys, compact separators, UTF-8."""
    return json.dumps(
        _normalise(obj, "$"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
