"""Atomic checkpoint files for the reference runtime.

A checkpoint is written as temp file -> ``fsync`` -> ``os.replace`` -> ``fsync``
of the directory. A crash at any point leaves either the previous checkpoint or
the new one, never a mixture.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


class CheckpointError(Exception):
    """The checkpoint cannot be used (for example an unknown schema version)."""


class CheckpointCorrupt(CheckpointError):
    """The checkpoint is truncated, damaged or fails its integrity digest."""


def _digest(body: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()


def write_checkpoint(path: str | Path, data: dict[str, Any]) -> None:
    """Atomically replace the checkpoint at ``path`` with ``data``."""
    target = Path(path)
    body = {"schema_version": SCHEMA_VERSION, **data}
    payload = {"body": body, "digest": _digest(body)}
    tmp = target.with_name(target.name + ".tmp")
    with open(tmp, "wb") as fh:
        fh.write(json.dumps(payload, sort_keys=True).encode("utf-8"))
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, target)
    dir_fd = os.open(target.parent, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def load_checkpoint(path: str | Path) -> dict[str, Any] | None:
    """Return the checkpoint contents, or ``None`` if none exists yet."""
    target = Path(path)
    try:
        raw = target.read_bytes()
    except FileNotFoundError:
        return None
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise CheckpointCorrupt(f"checkpoint {target} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict) or "body" not in data or "digest" not in data:
        raise CheckpointCorrupt(f"checkpoint {target} has no body and digest")
    body = data["body"]
    if not isinstance(body, dict) or _digest(body) != data["digest"]:
        raise CheckpointCorrupt(f"checkpoint {target} fails its integrity digest")
    data = body
    version = data.get("schema_version")
    if version != SCHEMA_VERSION:
        raise CheckpointError(
            f"unsupported checkpoint schema_version {version!r}; expected {SCHEMA_VERSION}"
        )
    return data
