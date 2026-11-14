"""Damage helpers for chaos tests: corrupt durable files the way a bad disk or crash would."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

#: Modes accepted by ``revenant run --chaos``.
CHAOS_MODES = ("none", "dup", "timeout", "corrupt", "all")
#: Environment variable carrying the injections a child process should apply.
CHAOS_ENV = "REVENANT_CHAOS"
#: Byte offset of the bit flipped by the ``corrupt`` mode (inside the checkpoint body).
CORRUPT_OFFSET = 10

_INJECTIONS = {
    "none": frozenset[str](),
    "dup": frozenset({"dup"}),
    "timeout": frozenset({"timeout"}),
    "corrupt": frozenset[str](),
    "all": frozenset({"dup", "timeout"}),
}


def injections(mode: str) -> frozenset[str]:
    """Runtime injections (``dup``, ``timeout``) a chaos mode switches on in the child."""
    try:
        return _INJECTIONS[mode]
    except KeyError:
        raise ValueError(f"unknown chaos mode {mode!r}; known: {', '.join(CHAOS_MODES)}") from None


def damages_checkpoint(mode: str) -> bool:
    """True when the mode corrupts the checkpoint between the kill and the resume."""
    injections(mode)
    return mode in ("corrupt", "all")


def injections_from_env(env: Mapping[str, str] | None = None) -> frozenset[str]:
    """Injections requested through ``REVENANT_CHAOS`` (comma separated)."""
    raw = (env if env is not None else os.environ).get(CHAOS_ENV, "")
    return frozenset(part for part in raw.split(",") if part)


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


def corrupt_checkpoint(workdir: str | Path, checkpoint_name: str = "checkpoint.json") -> bool:
    """Flip one bit of the checkpoint in ``workdir``; False if there is nothing to damage."""
    target = Path(workdir) / checkpoint_name
    if not target.exists() or target.stat().st_size <= CORRUPT_OFFSET:
        return False
    flip_bit(target, CORRUPT_OFFSET)
    return True
