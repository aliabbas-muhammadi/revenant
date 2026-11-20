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


def test_context_manager_closes_and_persists(tmp_path):
    path = tmp_path / "ctx.db"
    with Ledger(path) as ledger:
        ledger.begin("a", 1)
        ledger.commit("a")
    with Ledger(path) as again:
        assert again.status("a") == ("committed", 1)


def test_close_is_idempotent(tmp_path):
    ledger = Ledger(tmp_path / "c.db")
    ledger.close()
    ledger.close()


def test_entries_sorted_with_status_and_attempts(tmp_path):
    with Ledger(tmp_path / "l.db") as led:
        led.begin("b:1", {"x": 1})
        led.begin("a:1", {"x": 2})
        led.commit("a:1")
        led.begin("a:1", {"x": 2})
        assert led.entries() == [("a:1", "committed", 2), ("b:1", "intent", 1)]


def test_len_counts_keys_not_attempts(tmp_path):
    with Ledger(tmp_path / "l.db") as led:
        assert len(led) == 0
        led.begin("k", {})
        led.begin("k", {})
        led.begin("j", {})
        assert len(led) == 2


def test_status_of_unknown_key_is_none(tmp_path):
    with Ledger(tmp_path / "l.db") as led:
        assert led.status("nope") is None


def test_attempts_counts_and_defaults_to_zero(tmp_path):
    with Ledger(tmp_path / "l.db") as led:
        assert led.attempts("k") == 0
        led.begin("k", {})
        led.begin("k", {})
        assert led.attempts("k") == 2


def test_is_committed_follows_the_lifecycle(tmp_path):
    with Ledger(tmp_path / "l.db") as led:
        assert not led.is_committed("k")
        led.begin("k", {})
        assert not led.is_committed("k")
        led.commit("k")
        assert led.is_committed("k")


def test_keys_sorted_and_filtered_by_status(tmp_path):
    with Ledger(tmp_path / "l.db") as led:
        for key in ("b", "a", "c"):
            led.begin(key, {})
        led.commit("c")
        assert led.keys() == ["a", "b", "c"]
        assert led.keys("intent") == ["a", "b"]
        assert led.keys("committed") == ["c"]


def test_keys_rejects_unknown_status(tmp_path):
    with Ledger(tmp_path / "l.db") as led:
        with pytest.raises(ValueError):
            led.keys("pending")


def test_contains_reports_seen_keys(tmp_path):
    with Ledger(tmp_path / "l.db") as led:
        assert "k" not in led
        led.begin("k", {})
        assert "k" in led
        assert 5 not in led


def test_iter_yields_sorted_keys(tmp_path):
    with Ledger(tmp_path / "l.db") as led:
        for key in ("b", "a"):
            led.begin(key, {})
        assert list(led) == ["a", "b"]


def test_tools_lists_distinct_prefixes_sorted(ledger):
    assert ledger.tools() == []
    ledger.begin("send_email:2", {})
    ledger.begin("charge_card:1", {})
    ledger.begin("send_email:1", {})
    assert ledger.tools() == ["charge_card", "send_email"]


def test_count_by_status(ledger):
    assert ledger.count() == 0
    ledger.begin("a:1", {})
    ledger.begin("b:1", {})
    ledger.commit("a:1")
    assert ledger.count() == 2
    assert ledger.count("committed") == 1
    assert ledger.count("intent") == 1
    with pytest.raises(ValueError):
        ledger.count("bogus")


def test_reattempted_lists_keys_with_retries(ledger):
    assert ledger.reattempted() == []
    ledger.begin("b:1", {})
    ledger.begin("a:1", {})
    ledger.commit("a:1")
    assert ledger.reattempted() == []
    ledger.begin("a:1", {})
    ledger.begin("b:1", {})
    assert ledger.reattempted() == ["a:1", "b:1"]


def test_payload_hash_of_returns_stored_hash_or_none(tmp_path):
    with Ledger(tmp_path / "l.db") as ledger:
        assert ledger.payload_hash_of("a:1") is None
        ledger.begin("a:1", {"x": 1})
        assert ledger.payload_hash_of("a:1") == state_hash({"x": 1})
        ledger.begin("a:1", {"x": 1})
        assert ledger.payload_hash_of("a:1") == state_hash({"x": 1})


def test_has_unconfirmed_follows_intent_rows(tmp_path):
    with Ledger(tmp_path / "l.db") as led:
        assert not led.has_unconfirmed()
        led.begin("a:1", {"x": 1})
        assert led.has_unconfirmed()
        led.commit("a:1")
        assert not led.has_unconfirmed()


def test_max_attempts_tracks_the_busiest_key(tmp_path):
    with Ledger(tmp_path / "l.db") as ledger:
        assert ledger.max_attempts() == 0
        ledger.begin("a:1", {"x": 1})
        assert ledger.max_attempts() == 1
        ledger.begin("a:1", {"x": 1})
        ledger.begin("a:1", {"x": 1})
        ledger.begin("b:1", {"x": 2})
        assert ledger.max_attempts() == 3


def test_suppressed_keys_lists_retried_committed_keys(tmp_path):
    with Ledger(tmp_path / "l.db") as ledger:
        assert ledger.suppressed_keys() == []
        ledger.begin("a:1", {"x": 1})
        ledger.commit("a:1")
        ledger.begin("b:1", {"x": 2})
        ledger.commit("b:1")
        ledger.begin("b:1", {"x": 2})
        ledger.begin("c:1", {"x": 3})
        ledger.begin("c:1", {"x": 3})
        assert ledger.suppressed_keys() == ["b:1"]


def test_is_empty_until_first_begin(tmp_path):
    with Ledger(tmp_path / "l.db") as ledger:
        assert ledger.is_empty()
        ledger.begin("a:1", {"x": 1})
        assert not ledger.is_empty()


def test_status_counts_always_has_both_keys(ledger):
    assert ledger.status_counts() == {"intent": 0, "committed": 0}
    ledger.begin("a:1", {"x": 1})
    ledger.begin("b:1", {"x": 2})
    ledger.commit("a:1")
    assert ledger.status_counts() == {"intent": 1, "committed": 1}


def test_first_unconfirmed_is_smallest_intent_key(ledger):
    assert ledger.first_unconfirmed() is None
    ledger.begin("z:1", {"x": 1})
    ledger.begin("a:1", {"x": 2})
    assert ledger.first_unconfirmed() == "a:1"
    ledger.commit("a:1")
    assert ledger.first_unconfirmed() == "z:1"
    ledger.commit("z:1")
    assert ledger.first_unconfirmed() is None


def test_total_attempts_sums_every_key(ledger):
    assert ledger.total_attempts() == 0
    ledger.begin("a:1", {"n": 1})
    ledger.begin("b:1", {"n": 2})
    ledger.commit("a:1")
    ledger.begin("a:1", {"n": 1})  # suppressed re-attempt
    ledger.begin("b:1", {"n": 2})  # crash-residue re-attempt
    assert ledger.total_attempts() == 4
    assert ledger.total_attempts() == sum(n for _, _, n in ledger.entries())


def test_tool_counts_by_prefix_and_status(ledger):
    assert ledger.tool_counts() == {}
    ledger.begin("send_email:1", {"n": 1})
    ledger.begin("send_email:2", {"n": 2})
    ledger.begin("charge_card:1", {"n": 3})
    ledger.commit("send_email:1")
    assert ledger.tool_counts() == {"charge_card": 1, "send_email": 2}
    assert ledger.tool_counts("committed") == {"send_email": 1}
    assert ledger.tool_counts("intent") == {"charge_card": 1, "send_email": 1}


def test_tool_counts_rejects_unknown_status(ledger):
    with pytest.raises(ValueError):
        ledger.tool_counts("done")


def test_committed_and_intent_keys(ledger):
    assert ledger.committed_keys() == [] and ledger.intent_keys() == []
    ledger.begin("b:1", {"n": 1})
    ledger.begin("a:1", {"n": 2})
    ledger.begin("c:1", {"n": 3})
    ledger.commit("c:1")
    ledger.commit("b:1")
    assert ledger.committed_keys() == ["b:1", "c:1"]
    assert ledger.intent_keys() == ["a:1"] == ledger.unconfirmed()


def test_keys_for_filters_by_tool_prefix(ledger):
    ledger.begin("send_email:2", {"n": 1})
    ledger.begin("send_email:1", {"n": 2})
    ledger.begin("charge_card:1", {"n": 3})
    ledger.commit("send_email:1")
    assert ledger.keys_for("send_email") == ["send_email:1", "send_email:2"]
    assert ledger.keys_for("send_email", "committed") == ["send_email:1"]
    assert ledger.keys_for("send_email", "intent") == ["send_email:2"]
    assert ledger.keys_for("write_file") == []


def test_keys_for_does_not_match_prefix_substrings(ledger):
    ledger.begin("send:1", {"n": 1})
    ledger.begin("send_email:1", {"n": 2})
    assert ledger.keys_for("send") == ["send:1"]


def test_keys_for_rejects_unknown_status(ledger):
    with pytest.raises(ValueError):
        ledger.keys_for("send_email", "done")


def test_most_attempted_none_when_empty(ledger):
    assert ledger.most_attempted() is None


def test_most_attempted_picks_highest_attempt_count(ledger):
    ledger.begin("a:1", {"n": 1})
    ledger.begin("b:1", {"n": 2})
    ledger.begin("b:1", {"n": 2})
    ledger.begin("b:1", {"n": 2})
    assert ledger.most_attempted() == "b:1"


def test_most_attempted_breaks_ties_by_smallest_key(ledger):
    ledger.begin("b:1", {"n": 1})
    ledger.begin("a:1", {"n": 2})
    assert ledger.most_attempted() == "a:1"


def test_keys_with_attempts_filters_by_threshold(ledger):
    ledger.begin("a:1", {"n": 1})
    ledger.begin("b:1", {"n": 2})
    ledger.begin("b:1", {"n": 2})
    ledger.begin("c:1", {"n": 3})
    for _ in range(2):
        ledger.begin("c:1", {"n": 3})
    assert ledger.keys_with_attempts(1) == ["a:1", "b:1", "c:1"]
    assert ledger.keys_with_attempts(2) == ["b:1", "c:1"]
    assert ledger.keys_with_attempts(3) == ["c:1"]
    assert ledger.keys_with_attempts(4) == []


def test_keys_with_attempts_empty_ledger(ledger):
    assert ledger.keys_with_attempts(1) == []


def test_keys_with_attempts_rejects_small_n(ledger):
    for n in (0, -1):
        with pytest.raises(ValueError):
            ledger.keys_with_attempts(n)
