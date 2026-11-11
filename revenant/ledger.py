"""Effects ledger: a SQLite record of side effects, keyed by idempotency key.

The protocol is two-phase: record ``intent``, execute the effect, mark
``committed``. See DESIGN.md for the crash-window reasoning.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from revenant.canon import state_hash

SCHEMA = """
CREATE TABLE IF NOT EXISTS effects (
    idempotency_key TEXT PRIMARY KEY,
    payload_hash TEXT,
    status TEXT CHECK(status IN ('intent','committed')),
    attempt_count INTEGER
)
"""


class LedgerError(RuntimeError):
    """Raised on an invalid ledger operation."""


def payload_hash(payload: Any) -> str:
    """Hash a tool payload with the canonical state hash."""
    return state_hash(payload)


class Ledger:
    """SQLite-backed effects ledger in WAL mode with full fsync."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        # Autocommit mode: each operation opens its own explicit transaction.
        self._conn = sqlite3.connect(self.path, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.execute(SCHEMA)

    def pragma(self, name: str) -> Any:
        """Return the current value of a SQLite pragma (for tests and reports)."""
        return self._conn.execute(f"PRAGMA {name}").fetchone()[0]
