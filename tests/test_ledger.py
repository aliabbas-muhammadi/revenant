import os
import signal
import sqlite3
import subprocess
import sys

import pytest

from revenant.canon import state_hash
from revenant.ledger import (
    Decision,
    IdempotencyKeyReuse,
    Ledger,
    LedgerError,
    LedgerSummary,
    payload_hash,
)


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


def test_unconfirmed_lists_only_intent_keys(ledger):
    assert ledger.unconfirmed() == []
    ledger.begin("b", 1)
    ledger.begin("a", 2)
    ledger.begin("c", 3)
    ledger.commit("c")
    assert ledger.unconfirmed() == ["a", "b"]


def test_summary_empty(ledger):
    assert ledger.summary() == LedgerSummary(0, 0, 0, 0)


def test_summary_counts(ledger):
    ledger.begin("a", 1)
    ledger.commit("a")
    ledger.begin("a", 1)  # suppressed
    ledger.begin("a", 1)  # suppressed
    ledger.begin("b", 2)  # unconfirmed
    ledger.begin("c", 3)
    ledger.commit("c")
    assert ledger.summary() == LedgerSummary(attempts=5, effects=2, suppressed=2, unconfirmed=1)


def test_reopened_ledger_sees_committed_rows(tmp_path):
    path = tmp_path / "l.db"
    first = Ledger(path)
    first.begin("a", 1)
    first.commit("a")
    first.begin("b", 2)
    second = Ledger(path)  # no close on the first: each call is its own transaction
    assert second.status("a") == ("committed", 1)
    assert second.status("b") == ("intent", 1)
    assert second.unconfirmed() == ["b"]


def test_failed_operation_rolls_back(ledger):
    ledger.begin("k", {"a": 1})
    with pytest.raises(IdempotencyKeyReuse):
        ledger.begin("k", {"a": 2})
    assert not ledger._conn.in_transaction
    ledger.commit("k")


@pytest.mark.skipif(os.name != "posix", reason="needs POSIX SIGKILL")
def test_sigkill_after_intent_leaves_one_unconfirmed_key(tmp_path):
    path = tmp_path / "crash.db"
    code = (
        "import os, signal, sys\n"
        "from revenant.ledger import Ledger\n"
        "ledger = Ledger(sys.argv[1])\n"
        "ledger.begin('send-1', {'to': 'a@example.com'})\n"
        "os.kill(os.getpid(), signal.SIGKILL)\n"
    )
    proc = subprocess.run([sys.executable, "-c", code, str(path)], check=False)
    assert proc.returncode == -signal.SIGKILL
    reopened = Ledger(path)
    assert reopened.unconfirmed() == ["send-1"]
    assert reopened.status("send-1") == ("intent", 1)
