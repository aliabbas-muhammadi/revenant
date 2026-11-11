import sqlite3

import pytest

from revenant.canon import state_hash
from revenant.ledger import Ledger, payload_hash


@pytest.fixture
def ledger(tmp_path):
    return Ledger(tmp_path / "ledger.db")


def test_pragmas(ledger):
    assert ledger.pragma("journal_mode") == "wal"
    assert ledger.pragma("synchronous") == 2  # FULL


def test_effects_table_schema(ledger):
    cols = ledger._conn.execute("PRAGMA table_info(effects)").fetchall()
    assert [(c[1], c[2], c[5]) for c in cols] == [
        ("idempotency_key", "TEXT", 1),
        ("payload_hash", "TEXT", 0),
        ("status", "TEXT", 0),
        ("attempt_count", "INTEGER", 0),
    ]


def test_status_check_constraint(ledger):
    with pytest.raises(sqlite3.IntegrityError):
        ledger._conn.execute(
            "INSERT INTO effects VALUES ('k', 'h', 'bogus', 1)"
        )


def test_payload_hash_matches_state_hash():
    payload = {"to": "a@example.com", "n": 1}
    assert payload_hash(payload) == state_hash(payload)
    assert payload_hash({"b": 1, "a": 2}) == payload_hash({"a": 2, "b": 1})
