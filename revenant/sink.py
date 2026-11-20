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

    def last_for(self, tool: str) -> dict[str, Any] | None:
        """Return the most recent whole record naming ``tool``, or None if there is none."""
        matches = self.filter(tool)
        return matches[-1] if matches else None

    def first_for(self, tool: str) -> dict[str, Any] | None:
        """Return the earliest whole record naming ``tool``, or None if there is none."""
        matches = self.filter(tool)
        return matches[0] if matches else None

    def count(self, tool: str) -> int:
        """Count whole records whose ``tool`` field equals ``tool``."""
        return self.by_tool().get(tool, 0)

    def tools(self) -> list[str]:
        """Distinct ``tool`` values among whole records, sorted."""
        return list(self.by_tool())

    def has(self, tool: str) -> bool:
        """True when at least one whole record names ``tool``."""
        return self.count(tool) > 0

    def values(self, field: str) -> list[Any]:
        """Return the ``field`` value of every whole record that has it, in append order."""
        return [r[field] for r in self.read().effects if field in r]

    def filter(self, tool: str) -> list[dict[str, Any]]:
        """Return whole records whose ``tool`` field equals ``tool``, in append order."""
        return [r for r in self.read().effects if r.get("tool") == tool]

    def since(self, n: int) -> list[dict[str, Any]]:
        """Return whole records from index ``n`` onward; ``n`` must not be negative."""
        if n < 0:
            raise ValueError("since() index must not be negative")
        return self.read().effects[n:]

    def before(self, n: int) -> list[dict[str, Any]]:
        """Return whole records before index ``n``; ``n`` must not be negative."""
        if n < 0:
            raise ValueError("before() index must not be negative")
        return self.read().effects[:n]

    def tail(self, n: int) -> list[dict[str, Any]]:
        """Return the last ``n`` whole records in append order; ``n`` must not be negative."""
        if n < 0:
            raise ValueError("tail() count must not be negative")
        if n == 0:
            return []
        return self.read().effects[-n:]

    def fields(self) -> list[str]:
        """Return the distinct field names across every whole record, sorted."""
        names: set[str] = set()
        for record in self.read().effects:
            names.update(record)
        return sorted(names)

    def group_by(self, field: str) -> dict[Any, list[dict[str, Any]]]:
        """Map each value of ``field`` to its whole records, in append order.

        Records without the field are skipped. A value that cannot be a dict key
        (a list or dict) raises ``TypeError``.
        """
        groups: dict[Any, list[dict[str, Any]]] = {}
        for record in self.read().effects:
            if field in record:
                groups.setdefault(record[field], []).append(record)
        return groups

    def field_counts(self, field: str) -> dict[Any, int]:
        """Count whole records per value of ``field``, in first-seen order.

        Records without the field are skipped; an unhashable value raises ``TypeError``.
        """
        return {value: len(records) for value, records in self.group_by(field).items()}

    def duplicates(self) -> list[tuple[dict[str, Any], int]]:
        """Whole records that appear more than once, as ``(record, count)`` pairs.

        Pairs come in first-seen order. Two records are the same when they are equal
        as JSON, regardless of key order.
        """
        counts: dict[str, int] = {}
        first: dict[str, dict[str, Any]] = {}
        for record in self.read().effects:
            marker = json.dumps(record, sort_keys=True, ensure_ascii=False)
            counts[marker] = counts.get(marker, 0) + 1
            first.setdefault(marker, record)
        return [(first[m], n) for m, n in counts.items() if n > 1]

    def unique(self) -> list[dict[str, Any]]:
        """Whole records with repeats removed, keeping the first of each in append order.

        Records are the same when equal as JSON, regardless of key order, as in
        :meth:`duplicates`.
        """
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for record in self.read().effects:
            marker = json.dumps(record, sort_keys=True, ensure_ascii=False)
            if marker not in seen:
                seen.add(marker)
                out.append(record)
        return out

    def count_unique(self, tool: str | None = None) -> int:
        """Number of distinct whole records, optionally only those naming ``tool``."""
        records = self.unique()
        if tool is not None:
            records = [r for r in records if r.get("tool") == tool]
        return len(records)

    def contains(self, record: dict[str, Any]) -> bool:
        """True when an equal whole record exists, regardless of key order."""
        marker = json.dumps(record, sort_keys=True, ensure_ascii=False)
        return any(
            json.dumps(r, sort_keys=True, ensure_ascii=False) == marker
            for r in self.read().effects
        )

    def index_of(self, record: dict[str, Any]) -> int | None:
        """Return the index of the first whole record equal to ``record``, or None.

        Equality is as in :meth:`contains`: equal as JSON, regardless of key order.
        """
        marker = json.dumps(record, sort_keys=True, ensure_ascii=False)
        for index, candidate in enumerate(self.read().effects):
            if json.dumps(candidate, sort_keys=True, ensure_ascii=False) == marker:
                return index
        return None

    def is_empty(self) -> bool:
        """True when the sink holds no whole records."""
        return len(self) == 0
