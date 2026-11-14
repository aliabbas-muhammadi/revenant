"""Damage helpers for chaos tests: corrupt durable files the way a bad disk or crash would."""

from __future__ import annotations

from pathlib import Path


def truncate_file(path: str | Path, keep: int) -> None:
    """Cut ``path`` down to its first ``keep`` bytes."""
    target = Path(path)
    target.write_bytes(target.read_bytes()[:keep])


def flip_bit(path: str | Path, offset: int, bit: int = 0) -> None:
    """Invert one bit of the byte at ``offset``; a negative offset counts from the end."""
    target = Path(path)
    data = bytearray(target.read_bytes())
    data[offset] ^= 1 << bit
    target.write_bytes(bytes(data))
