"""Canonical JSON encoding used for state hashing.

Numbers keep their Python type: ``1`` encodes as ``1`` and ``1.0`` as ``1.0``,
so they hash differently. A runtime that silently turns an int into a float (or
back) across a checkpoint round-trip changed its state, and the harness should
report that rather than paper over it. ``True`` and ``False`` stay JSON booleans
and never collide with ``1`` and ``0``.
"""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from collections.abc import Iterable
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


def _matches(trail: tuple[str, ...], pattern: list[str]) -> bool:
    """Match a key path against a volatile pattern.

    A leading ``*`` segment matches any number of parent keys (including none),
    so ``*.ts`` matches a ``ts`` key at every depth.
    """
    if pattern and pattern[0] == "*":
        tail = pattern[1:]
        return bool(tail) and len(trail) >= len(tail) and list(trail[-len(tail):]) == tail
    return list(trail) == pattern


def _strip_volatile(obj: Any, patterns: list[list[str]], trail: tuple[str, ...]) -> Any:
    """Drop dict keys whose dotted path matches a volatile pattern.

    Paths are made of dict keys only; list positions are transparent, so
    ``items.ts`` addresses ``ts`` in every dict inside the ``items`` list.
    A leading ``*`` makes the pattern match at any depth.
    """
    if isinstance(obj, dict):
        out: dict[Any, Any] = {}
        for key, value in obj.items():
            here = (*trail, _nfc(key) if isinstance(key, str) else str(key))
            if any(_matches(here, pat) for pat in patterns):
                continue
            out[key] = _strip_volatile(value, patterns, here)
        return out
    if isinstance(obj, list | tuple):
        return [_strip_volatile(v, patterns, trail) for v in obj]
    return obj


def state_hash(obj: Any, volatile_fields: Iterable[str] = ()) -> str:
    """Return the SHA-256 hex digest of the canonical encoding of ``obj``.

    ``volatile_fields`` lists dotted paths (for example ``"meta.ts"``) that are
    excluded before hashing, so timestamps and durations do not make a resumed
    run look divergent.
    """
    patterns = [p.split(".") for p in volatile_fields]
    if patterns:
        obj = _strip_volatile(obj, patterns, ())
    return hashlib.sha256(canonical_json(obj)).hexdigest()
