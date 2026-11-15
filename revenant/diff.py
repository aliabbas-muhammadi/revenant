"""Compare two saved JSON reports boundary by boundary."""

from __future__ import annotations

from typing import Any

VOLATILE = frozenset({"wall_seconds"})


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    """Flatten nested dicts to dotted paths; lists and scalars are leaves."""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if key in VOLATILE:
                continue
            out.update(_flatten(item, f"{prefix}.{key}" if prefix else str(key)))
        return out
    return {prefix: value}


def diff_reports(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    """Return human-readable differences between two reports; empty means equivalent."""
    lines: list[str] = []
    for key in ("adapter", "workload", "verdict"):
        if a.get(key) != b.get(key):
            lines.append(f"{key}: {a.get(key)!r} -> {b.get(key)!r}")
    left = {x["boundary"]: x for x in a.get("boundaries", [])}
    right = {x["boundary"]: x for x in b.get("boundaries", [])}
    for number in sorted(left.keys() | right.keys()):
        if number not in right:
            lines.append(f"boundary {number}: only in A")
            continue
        if number not in left:
            lines.append(f"boundary {number}: only in B")
            continue
        fa, fb = _flatten(left[number]), _flatten(right[number])
        for path in sorted(fa.keys() | fb.keys()):
            if fa.get(path) != fb.get(path):
                lines.append(f"boundary {number}: {path}: {fa.get(path)!r} -> {fb.get(path)!r}")
    return lines
