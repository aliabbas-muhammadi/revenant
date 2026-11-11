import sqlite3

import pytest

from revenant.canon import state_hash
from revenant.ledger import Decision, IdempotencyKeyReuse, Ledger, LedgerError, payload_hash


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


def test_begin_new_key_inserts_intent_and_executes(ledger):
    assert ledger.begin("k1", {"to": "a"}) is Decision.EXECUTE
    assert ledger.status("k1") == ("intent", 1)
    row = ledger._conn.execute(
        "SELECT payload_hash FROM effects WHERE idempotency_key = 'k1'"
    ).fetchone()
    assert row[0] == payload_hash({"to": "a"})


def test_begin_distinct_keys_are_independent(ledger):
    assert ledger.begin("a", 1) is Decision.EXECUTE
    assert ledger.begin("b", 2) is Decision.EXECUTE
    assert ledger.status("a") == ("intent", 1)
    assert ledger.status("b") == ("intent", 1)


def test_commit_moves_intent_to_committed(ledger):
    ledger.begin("k", {})
    ledger.commit("k")
    assert ledger.status("k") == ("committed", 1)


def test_commit_unknown_key_raises(ledger):
    with pytest.raises(LedgerError):
        ledger.commit("nope")


def test_commit_twice_raises(ledger):
    ledger.begin("k", {})
    ledger.commit("k")
    with pytest.raises(LedgerError):
        ledger.commit("k")
    assert ledger.status("k") == ("committed", 1)


def test_reattempt_on_committed_key_is_suppressed(ledger):
    ledger.begin("k", {"a": 1})
    ledger.commit("k")
    assert ledger.begin("k", {"a": 1}) is Decision.SUPPRESS
    assert ledger.begin("k", {"a": 1}) is Decision.SUPPRESS
    assert ledger.status("k") == ("committed", 3)


def test_reattempt_on_intent_key_executes_again(ledger):
    ledger.begin("k", {"a": 1})
    assert ledger.begin("k", {"a": 1}) is Decision.EXECUTE
    assert ledger.status("k") == ("intent", 2)
    ledger.commit("k")
    assert ledger.status("k") == ("committed", 2)


def test_key_reuse_with_different_payload_raises_and_leaves_row(ledger):
    ledger.begin("k", {"a": 1})
    with pytest.raises(IdempotencyKeyReuse):
        ledger.begin("k", {"a": 2})
    assert ledger.status("k") == ("intent", 1)
    ledger.commit("k")
    with pytest.raises(IdempotencyKeyReuse):
        ledger.begin("k", {"a": 2})
    assert ledger.status("k") == ("committed", 1)


def test_key_reuse_is_a_ledger_error(ledger):
    assert issubclass(IdempotencyKeyReuse, LedgerError)
