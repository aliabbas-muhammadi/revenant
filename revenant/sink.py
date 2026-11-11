"""Effect sink: an append-only JSONL file standing in for the outside world.

Tools write their real effects here, independent of the ledger, so a duplicate
effect is observable even when a runtime bypasses the ledger entirely.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


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

    def effects(self) -> list[dict[str, Any]]:
        """Read every record back, in append order. A missing file is empty."""
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]
