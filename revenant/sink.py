"""Effect sink: an append-only JSONL file standing in for the outside world.

Tools write their real effects here, independent of the ledger, so a duplicate
effect is observable even when a runtime bypasses the ledger entirely.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class SinkCorrupt(ValueError):
    """The sink holds a line that is not a complete JSON record."""


@dataclass(frozen=True)
class SinkRead:
    """Everything readable from a sink: whole records plus any torn final line."""

    effects: list[dict[str, Any]]
    #: Text after the last newline that does not end a record (a write cut short), if any.
    partial: str | None = None


class EffectSink:
    """Append-only, fsynced JSONL record of effects that really happened."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: dict[str, Any]) -> None:
        """Append one record and fsync it before returning."""
        line = json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n"
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, line.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)

    def read(self) -> SinkRead:
        """Read whole records back and report a torn final line instead of failing on it.

        A line that ends in a newline must be valid JSON, otherwise ``SinkCorrupt``
        names its line number. Text after the last newline is the partial record.
        """
        if not self.path.exists():
            return SinkRead([])
        text = self.path.read_bytes().decode("utf-8", errors="replace")
        body, _, tail = text.rpartition("\n")
        records: list[dict[str, Any]] = []
        for number, line in enumerate(body.split("\n") if body else [], 1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except ValueError as exc:
                raise SinkCorrupt(f"{self.path} line {number} is not valid JSON: {exc}") from exc
        if tail.strip():
            try:
                records.append(json.loads(tail))
            except ValueError:
                return SinkRead(records, partial=tail)
        return SinkRead(records)

    def effects(self) -> list[dict[str, Any]]:
        """Read every record back, in append order. A missing file is empty.

        A torn final line raises ``SinkCorrupt``; use :meth:`read` to inspect it.
        """
        result = self.read()
        if result.partial is not None:
            raise SinkCorrupt(f"{self.path} ends in a partial record: {result.partial!r}")
        return result.effects
