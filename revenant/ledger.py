"""Effects ledger: a SQLite record of side effects, keyed by idempotency key.

The protocol is two-phase: record ``intent``, execute the effect, mark
``committed``. See DESIGN.md for the crash-window reasoning.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
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


class LedgerLost(LedgerError):
    """The ledger file vanished while a checkpoint says effects may already have run.

    Starting a fresh ledger would forget which keys are committed and silently
    re-run their effects, so a resume refuses to continue instead.
    """


class IdempotencyKeyReuse(LedgerError):
    """Raised when a key is reused with a different payload hash."""


class Decision(Enum):
    """What the caller should do with an attempted effect."""

    EXECUTE = "execute"
    SUPPRESS = "suppress"


def payload_hash(payload: Any) -> str:
    """Hash a tool payload with the canonical state hash."""
    return state_hash(payload)


@dataclass(frozen=True)
class LedgerSummary:
    """Aggregate counts, kept separate because attempts are not effects.

    ``suppressed`` is the number of attempts beyond the first on committed keys.
    The schema stores one counter per key, so a retry that executed again after
    crash residue and then committed is counted here too; it is an upper bound.
    """

    attempts: int
    effects: int
    suppressed: int
    unconfirmed: int


class Ledger:
    """SQLite-backed effects ledger in WAL mode with full fsync."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        # Autocommit mode: each operation opens its own explicit transaction.
        self._conn = sqlite3.connect(self.path, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.execute(SCHEMA)

    def close(self) -> None:
        """Close the connection. Safe to call more than once."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None  # type: ignore[assignment]

    def __enter__(self) -> Ledger:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def pragma(self, name: str) -> Any:
        """Return the current value of a SQLite pragma (for tests and reports)."""
        return self._conn.execute(f"PRAGMA {name}").fetchone()[0]

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        """Run one operation in its own immediate transaction."""
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield self._conn
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        self._conn.execute("COMMIT")

    def begin(self, key: str, payload: Any) -> Decision:
        """Record an attempt to perform the effect named by ``key``.

        - New key: insert an ``intent`` row (attempt 1) and return ``EXECUTE``.
        - ``committed`` key: the effect already happened, so increment the
          attempt count and return ``SUPPRESS``.
        - ``intent`` key: crash residue. The earlier attempt may or may not have
          performed the effect, and the ledger cannot know which. Executing again
          favours at-least-once; the row stays ``intent`` until a commit, and the
          harness reports it as unconfirmed rather than guessing.
        - Same key, different payload hash: ``IdempotencyKeyReuse``, with the row
          left untouched.
        """
        digest = payload_hash(payload)
        with self._tx() as conn:
            row = conn.execute(
                "SELECT payload_hash, status FROM effects WHERE idempotency_key = ?",
                (key,),
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO effects VALUES (?, ?, 'intent', 1)", (key, digest)
                )
                return Decision.EXECUTE
            stored_hash, status = row
            if stored_hash != digest:
                raise IdempotencyKeyReuse(
                    f"key {key!r} reused with a different payload"
                )
            conn.execute(
                "UPDATE effects SET attempt_count = attempt_count + 1 "
                "WHERE idempotency_key = ?",
                (key,),
            )
        return Decision.SUPPRESS if status == "committed" else Decision.EXECUTE

    def commit(self, key: str) -> None:
        """Mark the effect for ``key`` as committed (it happened)."""
        with self._tx() as conn:
            cur = conn.execute(
                "UPDATE effects SET status = 'committed' "
                "WHERE idempotency_key = ? AND status = 'intent'",
                (key,),
            )
            if cur.rowcount != 1:
                raise LedgerError(f"cannot commit {key!r}: unknown or already committed")

    def status(self, key: str) -> tuple[str, int] | None:
        """Return ``(status, attempt_count)`` for ``key``, or None if unknown."""
        row = self._conn.execute(
            "SELECT status, attempt_count FROM effects WHERE idempotency_key = ?", (key,)
        ).fetchone()
        return None if row is None else (row[0], row[1])

    def payload_hash_of(self, key: str) -> str | None:
        """Stored payload hash for ``key``, or None if the ledger has never seen it."""
        row = self._conn.execute(
            "SELECT payload_hash FROM effects WHERE idempotency_key = ?", (key,)
        ).fetchone()
        return None if row is None else str(row[0])

    def attempts(self, key: str) -> int:
        """Attempt count for ``key``; ``0`` for a key the ledger has never seen."""
        state = self.status(key)
        return 0 if state is None else state[1]

    def is_committed(self, key: str) -> bool:
        """True once ``key`` has been committed; unknown and intent keys are False."""
        state = self.status(key)
        return state is not None and state[0] == "committed"

    def keys(self, status: str | None = None) -> list[str]:
        """Keys sorted ascending, optionally only those in ``status``."""
        if status is not None and status not in ("intent", "committed"):
            raise ValueError(f"unknown status {status!r}")
        return [key for key, state, _ in self.entries() if status in (None, state)]

    def tools(self) -> list[str]:
        """Distinct tool names, taken from the ``tool:`` prefix of each key, sorted."""
        return sorted({key.partition(":")[0] for key in self.keys()})

    def __contains__(self, key: object) -> bool:
        """True when the ledger has any row for ``key``."""
        return isinstance(key, str) and self.status(key) is not None

    def __iter__(self) -> Iterator[str]:
        """Iterate over every key, sorted ascending."""
        return iter(self.keys())

    def entries(self) -> list[tuple[str, str, int]]:
        """Every row as ``(key, status, attempt_count)``, sorted by key."""
        rows = self._conn.execute(
            "SELECT idempotency_key, status, attempt_count FROM effects "
            "ORDER BY idempotency_key"
        ).fetchall()
        return [(r[0], r[1], r[2]) for r in rows]

    def __len__(self) -> int:
        """Number of distinct idempotency keys recorded."""
        return int(self._conn.execute("SELECT COUNT(*) FROM effects").fetchone()[0])

    def is_empty(self) -> bool:
        """True when the ledger has recorded no keys."""
        return len(self) == 0

    def count(self, status: str | None = None) -> int:
        """Number of rows, optionally only those in ``status``."""
        if status is None:
            return len(self)
        return len(self.keys(status))

    def status_counts(self) -> dict[str, int]:
        """Rows per status; both ``intent`` and ``committed`` are always present."""
        return {"intent": self.count("intent"), "committed": self.count("committed")}

    def first_unconfirmed(self) -> str | None:
        """The smallest key still in ``intent``, or None when nothing is unconfirmed."""
        pending = self.unconfirmed()
        return pending[0] if pending else None

    def max_attempts(self) -> int:
        """The highest attempt count on any key; ``0`` for an empty ledger."""
        row = self._conn.execute("SELECT COALESCE(MAX(attempt_count), 0) FROM effects").fetchone()
        return int(row[0])

    def suppressed_keys(self) -> list[str]:
        """Committed keys that were attempted again after committing, sorted.

        Like ``LedgerSummary.suppressed`` this is an upper bound: a retry that
        re-executed crash residue before the commit is counted too.
        """
        return [k for k, status, n in self.entries() if status == "committed" and n > 1]

    def reattempted(self) -> list[str]:
        """Keys attempted more than once (retries, suppressed or not), sorted."""
        return [key for key, _, attempts in self.entries() if attempts > 1]

    def unconfirmed(self) -> list[str]:
        """Keys still in ``intent``: executed-or-not is unknown. Never auto-resolved."""
        rows = self._conn.execute(
            "SELECT idempotency_key FROM effects WHERE status = 'intent' "
            "ORDER BY idempotency_key"
        ).fetchall()
        return [r[0] for r in rows]

    def has_unconfirmed(self) -> bool:
        """True while any key is still in ``intent``."""
        return self.count("intent") > 0

    def attempts_by_tool(self) -> dict[str, int]:
        """Attempts per tool, taken from the ``tool:`` prefix of each idempotency key."""
        out: dict[str, int] = {}
        for key, count in self._conn.execute("SELECT idempotency_key, attempt_count FROM effects"):
            tool = key.partition(":")[0]
            out[tool] = out.get(tool, 0) + count
        return out

    def attempt_histogram(self) -> dict[int, int]:
        """How many committed effects took 1, 2, 3... attempts (``{attempts: effects}``)."""
        rows = self._conn.execute(
            "SELECT attempt_count, COUNT(*) FROM effects WHERE status = 'committed' "
            "GROUP BY attempt_count ORDER BY attempt_count"
        ).fetchall()
        return {int(n): int(c) for n, c in rows}

    def summary(self) -> LedgerSummary:
        """Return attempts, committed effects, suppressed attempts and unconfirmed keys."""
        row = self._conn.execute(
            "SELECT COALESCE(SUM(attempt_count), 0),"
            " COALESCE(SUM(status = 'committed'), 0),"
            " COALESCE(SUM(CASE WHEN status = 'committed' THEN attempt_count - 1 END), 0),"
            " COALESCE(SUM(status = 'intent'), 0)"
            " FROM effects"
        ).fetchone()
        return LedgerSummary(*row)
