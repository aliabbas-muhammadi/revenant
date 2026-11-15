"""Reference runtime variant that keeps its checkpoint inside the SQLite ledger.

State and effects share one database file, so a checkpoint write is a single
SQLite transaction: it either lands whole or not at all. ``REVENANT_KILL_AT_WRITE``
points map onto that transaction: 1 after ``BEGIN``, 2 after the row is written,
3 after ``COMMIT``, 4 after the WAL is checkpointed into the main file.
"""

from __future__ import annotations

import os
import signal
from pathlib import Path
from typing import Any

from revenant.adapters.reference import LEDGER_NAME, ReferenceAdapter, main
from revenant.checkpoint import WRITE_POINTS, decode_checkpoint, encode_checkpoint
from revenant.ledger import Ledger

CHECKPOINT_SCHEMA = """
CREATE TABLE IF NOT EXISTS checkpoint (
    id INTEGER PRIMARY KEY CHECK(id = 1),
    body BLOB NOT NULL
)
"""


def _die_at(kill_point: int | None, point: int) -> None:
    if kill_point == point:
        os.kill(os.getpid(), signal.SIGKILL)


class SqliteStore(Ledger):
    """A :class:`Ledger` that also holds the checkpoint in the same database."""

    def __init__(self, path: str | Path) -> None:
        super().__init__(path)
        self._conn.execute(CHECKPOINT_SCHEMA)

    def save_checkpoint(self, data: dict[str, Any], kill_point: int | None = None) -> None:
        """Replace the stored checkpoint in one transaction."""
        if kill_point is not None and kill_point not in WRITE_POINTS:
            raise ValueError(f"kill_point must be one of {WRITE_POINTS}, got {kill_point!r}")
        with self._tx() as conn:
            _die_at(kill_point, 1)
            conn.execute(
                "INSERT OR REPLACE INTO checkpoint (id, body) VALUES (1, ?)",
                (encode_checkpoint(data),),
            )
            _die_at(kill_point, 2)
        _die_at(kill_point, 3)
        self._conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
        _die_at(kill_point, 4)

    def load_checkpoint(self) -> dict[str, Any] | None:
        """Return the stored checkpoint, or ``None`` if none was written."""
        row = self._conn.execute("SELECT body FROM checkpoint WHERE id = 1").fetchone()
        if row is None:
            return None
        return decode_checkpoint(bytes(row[0]), f"{self.path}:checkpoint")


class SqliteReferenceAdapter(ReferenceAdapter):
    """Reference step loop whose checkpoint lives in ``ledger.db``."""

    name = "reference_sqlite"

    def __init__(self) -> None:
        super().__init__()
        self._store: SqliteStore | None = None

    def _open_store(self, root: Path) -> SqliteStore:
        if self._store is None:
            self._store = SqliteStore(root / LEDGER_NAME)
        return self._store

    def _open_ledger(self, root: Path) -> Ledger:
        return self._open_store(root)

    def _load_saved(self, root: Path) -> dict[str, Any] | None:
        if not (root / LEDGER_NAME).exists():
            return None
        return self._open_store(root).load_checkpoint()

    def _write_checkpoint(self, path: Path, data: dict[str, Any], dying: bool) -> None:
        assert self._store is not None
        self._store.save_checkpoint(data, kill_point=self._kill_write if dying else None)

    @staticmethod
    def _forget_local_state(root: Path) -> None:
        for suffix in ("", "-wal", "-shm"):
            (root / (LEDGER_NAME + suffix)).unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main(adapter_cls=SqliteReferenceAdapter))
