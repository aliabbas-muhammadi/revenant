"""Reference runtime variant that keeps its checkpoint inside the SQLite ledger.

State and effects share one database file, so a checkpoint write is a single
SQLite transaction: it either lands whole or not at all. ``REVENANT_KILL_AT_WRITE``
points map onto that transaction: 1 after ``BEGIN``, 2 after the row is written,
3 after ``COMMIT``, 4 after the WAL is checkpointed into the main file.

``SqliteOutboxAdapter`` goes one step further: a step's tool call is not performed
inline. Its payload is queued in an ``outbox`` table in the same transaction as the
checkpoint, and a dispatcher performs queued calls only after that transaction
commits, so a checkpoint can never promise an effect that was not recorded.
"""

from __future__ import annotations

import json
import os
import signal
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from revenant.adapters.reference import LEDGER_NAME, ReferenceAdapter, main
from revenant.checkpoint import WRITE_POINTS, decode_checkpoint, encode_checkpoint
from revenant.ledger import Ledger
from revenant.sink import EffectSink
from revenant.tools import AttemptCounter, get_tool, invoke

CHECKPOINT_SCHEMA = """
CREATE TABLE IF NOT EXISTS checkpoint (
    id INTEGER PRIMARY KEY CHECK(id = 1),
    body BLOB NOT NULL
)
"""

OUTBOX_SCHEMA = """
CREATE TABLE IF NOT EXISTS outbox (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    idempotency_key TEXT NOT NULL UNIQUE,
    payload TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending','delivered'))
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
        self._conn.execute(OUTBOX_SCHEMA)

    def save_checkpoint(
        self,
        data: dict[str, Any],
        kill_point: int | None = None,
        outbox: Sequence[tuple[str, dict[str, Any]]] = (),
    ) -> None:
        """Replace the stored checkpoint, and queue ``outbox`` rows, in one transaction."""
        if kill_point is not None and kill_point not in WRITE_POINTS:
            raise ValueError(f"kill_point must be one of {WRITE_POINTS}, got {kill_point!r}")
        with self._tx() as conn:
            _die_at(kill_point, 1)
            conn.execute(
                "INSERT OR REPLACE INTO checkpoint (id, body) VALUES (1, ?)",
                (encode_checkpoint(data),),
            )
            for key, payload in outbox:
                conn.execute(
                    "INSERT OR IGNORE INTO outbox (idempotency_key, payload, status)"
                    " VALUES (?, ?, 'pending')",
                    (key, json.dumps(payload, sort_keys=True)),
                )
            _die_at(kill_point, 2)
        _die_at(kill_point, 3)
        self._conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
        _die_at(kill_point, 4)

    def pending(self) -> list[tuple[str, dict[str, Any]]]:
        """Queued calls not yet delivered, oldest first."""
        rows = self._conn.execute(
            "SELECT idempotency_key, payload FROM outbox WHERE status = 'pending' ORDER BY seq"
        ).fetchall()
        return [(key, json.loads(payload)) for key, payload in rows]

    def mark_delivered(self, key: str) -> None:
        """Record that the queued call for ``key`` has been dispatched."""
        with self._tx() as conn:
            conn.execute(
                "UPDATE outbox SET status = 'delivered' WHERE idempotency_key = ?", (key,)
            )

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


class SqliteOutboxAdapter(SqliteReferenceAdapter):
    """Outbox pattern: tool calls are queued with the checkpoint and dispatched after it."""

    name = "reference_outbox"

    def __init__(self) -> None:
        super().__init__()
        self._queued: list[tuple[str, dict[str, Any]]] = []
        self._attempts = AttemptCounter()

    def _call_tool(
        self,
        tool: Any,
        args: dict[str, Any],
        ledger: Ledger,
        sink: EffectSink,
        attempts: AttemptCounter,
    ) -> str:
        key: str = tool.idempotency_key(args)
        self._queued.append((key, {"tool": tool.name, "args": args}))
        return key

    def _write_checkpoint(self, path: Path, data: dict[str, Any], dying: bool) -> None:
        assert self._store is not None
        queued, self._queued = self._queued, []
        self._store.save_checkpoint(
            data, kill_point=self._kill_write if dying else None, outbox=queued
        )
        self._dispatch()

    def _dispatch(self) -> None:
        """Perform every queued call that has not been delivered yet."""
        assert self._store is not None and self._workdir is not None
        sink = EffectSink(self._workdir / "effects.jsonl")
        for key, call in self._store.pending():
            tool = get_tool(call["tool"], self._workdir / "sandbox")
            invoke(tool, call["args"], sink, self._store, self._attempts)
            self._store.mark_delivered(key)


if __name__ == "__main__":
    raise SystemExit(main(adapter_cls=SqliteReferenceAdapter))
