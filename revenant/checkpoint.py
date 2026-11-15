"""Atomic checkpoint files for the reference runtime.

A checkpoint is written as temp file -> ``fsync`` -> ``os.replace`` -> ``fsync``
of the directory. A crash at any point leaves either the previous checkpoint or
the new one, never a mixture.
"""

from __future__ import annotations

import hashlib
import json
import os
import signal
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

#: Points inside ``write_checkpoint`` where a kill can be requested, in order:
#: 1 temp file written, 2 temp file fsynced, 3 renamed over the target,
#: 4 directory fsynced (the write is fully durable).
WRITE_POINTS = (1, 2, 3, 4)


class CheckpointError(Exception):
    """The checkpoint cannot be used (for example an unknown schema version)."""


class CheckpointCorrupt(CheckpointError):
    """The checkpoint is truncated, damaged or fails its integrity digest."""


def _digest(body: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()


def _die_at(kill_point: int | None, point: int) -> None:
    if kill_point == point:
        os.kill(os.getpid(), signal.SIGKILL)


def encode_checkpoint(data: dict[str, Any]) -> bytes:
    """Serialise ``data`` with its schema version and integrity digest."""
    body = {"schema_version": SCHEMA_VERSION, **data}
    payload = {"body": body, "digest": _digest(body)}
    return json.dumps(payload, sort_keys=True).encode("utf-8")


def write_checkpoint(
    path: str | Path, data: dict[str, Any], kill_point: int | None = None
) -> None:
    """Atomically replace the checkpoint at ``path`` with ``data``.

    ``kill_point`` (one of ``WRITE_POINTS``) makes the process SIGKILL itself at
    that point of the write, to prove a crash anywhere leaves a usable checkpoint.
    """
    if kill_point is not None and kill_point not in WRITE_POINTS:
        raise ValueError(f"kill_point must be one of {WRITE_POINTS}, got {kill_point!r}")
    target = Path(path)
    tmp = target.with_name(target.name + ".tmp")
    with open(tmp, "wb") as fh:
        fh.write(encode_checkpoint(data))
        fh.flush()
        _die_at(kill_point, 1)
        os.fsync(fh.fileno())
        _die_at(kill_point, 2)
    os.replace(tmp, target)
    _die_at(kill_point, 3)
    dir_fd = os.open(target.parent, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)
    _die_at(kill_point, 4)


def load_checkpoint(path: str | Path) -> dict[str, Any] | None:
    """Return the checkpoint contents, or ``None`` if none exists yet."""
    target = Path(path)
    try:
        raw = target.read_bytes()
    except FileNotFoundError:
        return None
    return decode_checkpoint(raw, str(target))


def decode_checkpoint(raw: bytes, source: str) -> dict[str, Any]:
    """Parse and verify checkpoint bytes read from ``source``."""
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise CheckpointCorrupt(f"checkpoint {source} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict) or "body" not in data or "digest" not in data:
        raise CheckpointCorrupt(f"checkpoint {source} has no body and digest")
    body = data["body"]
    if not isinstance(body, dict) or _digest(body) != data["digest"]:
        raise CheckpointCorrupt(f"checkpoint {source} fails its integrity digest")
    data = body
    version = data.get("schema_version")
    if version != SCHEMA_VERSION:
        raise CheckpointError(
            f"unsupported checkpoint schema_version {version!r}; expected {SCHEMA_VERSION}"
        )
    return data
