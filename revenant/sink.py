"""Effect sink: an append-only JSONL file standing in for the outside world.

Tools write their real effects here, independent of the ledger, so a duplicate
effect is observable even when a runtime bypasses the ledger entirely.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
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

    def __len__(self) -> int:
        """Count whole records; a torn final line is not counted."""
        return len(self.read().effects)

    def by_tool(self) -> dict[str, int]:
        """Count records per ``tool`` field, sorted by tool name.

        Records without a ``tool`` field are not counted.
        """
        counts: dict[str, int] = {}
        for record in self.read().effects:
            tool = record.get("tool")
            if isinstance(tool, str):
                counts[tool] = counts.get(tool, 0) + 1
        return dict(sorted(counts.items()))

    def __iter__(self) -> Iterator[dict[str, Any]]:
        """Iterate over whole records in append order (a torn final line is skipped)."""
        return iter(self.read().effects)

    def last(self) -> dict[str, Any] | None:
        """Return the most recent whole record, or None when the sink is empty."""
        effects = self.read().effects
        return effects[-1] if effects else None

    def first(self) -> dict[str, Any] | None:
        """Return the earliest whole record, or None when the sink is empty."""
        effects = self.read().effects
        return effects[0] if effects else None

    def count(self, tool: str) -> int:
        """Count whole records whose ``tool`` field equals ``tool``."""
        return self.by_tool().get(tool, 0)

    def tools(self) -> list[str]:
        """Distinct ``tool`` values among whole records, sorted."""
        return list(self.by_tool())

    def has(self, tool: str) -> bool:
        """True when at least one whole record names ``tool``."""
        return self.count(tool) > 0

    def filter(self, tool: str) -> list[dict[str, Any]]:
        """Return whole records whose ``tool`` field equals ``tool``, in append order."""
        return [r for r in self.read().effects if r.get("tool") == tool]

    def since(self, n: int) -> list[dict[str, Any]]:
        """Return whole records from index ``n`` onward; ``n`` must not be negative."""
        if n < 0:
            raise ValueError("since() index must not be negative")
        return self.read().effects[n:]

    def tail(self, n: int) -> list[dict[str, Any]]:
        """Return the last ``n`` whole records in append order; ``n`` must not be negative."""
        if n < 0:
            raise ValueError("tail() count must not be negative")
        if n == 0:
            return []
        return self.read().effects[-n:]

    def is_empty(self) -> bool:
        """True when the sink holds no whole records."""
        return len(self) == 0
