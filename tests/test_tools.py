from typing import Any

import pytest

from revenant.ledger import IdempotencyKeyReuse, Ledger
from revenant.sink import EffectSink
from revenant.tools import AttemptCounter, SendEmail, Tool, invoke


class FakeTool(Tool):
    name = "fake"

    def idempotency_key(self, args: dict[str, Any]) -> str:
        return f"fake:{args['id']}"

    def perform(self, args: dict[str, Any], sink: EffectSink) -> Any:
        sink.append({"tool": self.name, **args})
        return "done"


@pytest.fixture
def env(tmp_path):
    with Ledger(tmp_path / "l.db") as ledger:
        yield ledger, EffectSink(tmp_path / "s.jsonl")


def test_tool_is_abstract():
    with pytest.raises(TypeError):
        Tool()  # type: ignore[abstract]


def test_first_call_executes_and_commits(env):
    ledger, sink = env
    out = invoke(FakeTool(), {"id": 1}, sink, ledger)
    assert out.executed and out.result == "done" and out.key == "fake:1"
    assert len(sink.effects()) == 1
    assert ledger.status("fake:1") == ("committed", 1)


def test_repeat_is_suppressed(env):
    ledger, sink = env
    invoke(FakeTool(), {"id": 1}, sink, ledger)
    again = invoke(FakeTool(), {"id": 1}, sink, ledger)
    assert not again.executed
    assert len(sink.effects()) == 1
    assert ledger.status("fake:1") == ("committed", 2)


def test_crash_residue_is_retried(env):
    ledger, sink = env
    ledger.begin("fake:1", {"tool": "fake", "args": {"id": 1}})  # crash after intent
    out = invoke(FakeTool(), {"id": 1}, sink, ledger)
    assert out.executed
    assert ledger.unconfirmed() == []


def test_key_reuse_with_new_args_fails(env):
    ledger, sink = env

    class Reuse(FakeTool):
        def idempotency_key(self, args):
            return "same"

    invoke(Reuse(), {"id": 1}, sink, ledger)
    with pytest.raises(IdempotencyKeyReuse):
        invoke(Reuse(), {"id": 2}, sink, ledger)
    assert len(sink.effects()) == 1


def test_attempts_count_every_call_independent_of_ledger_and_sink(env):
    ledger, sink = env
    attempts = AttemptCounter()
    for _ in range(3):
        invoke(FakeTool(), {"id": 1}, sink, ledger, attempts)
    invoke(FakeTool(), {"id": 2}, sink, ledger, attempts)
    assert attempts.count("fake") == 4
    assert attempts.total == 4
    assert attempts.by_tool() == {"fake": 4}
    assert len(sink.effects()) == 2


def test_attempt_is_counted_even_when_key_reuse_fails(env):
    ledger, sink = env
    attempts = AttemptCounter()

    class Reuse(FakeTool):
        def idempotency_key(self, args):
            return "same"

    invoke(Reuse(), {"id": 1}, sink, ledger, attempts)
    with pytest.raises(IdempotencyKeyReuse):
        invoke(Reuse(), {"id": 2}, sink, ledger, attempts)
    assert attempts.count("fake") == 2


def test_naive_mode_bypasses_ledger_and_duplicates_effects(tmp_path):
    args = {"to": "a@x", "subject": "s", "body": "b"}
    sink = EffectSink(tmp_path / "s.jsonl")
    attempts = AttemptCounter()
    with Ledger(tmp_path / "l.db") as ledger:
        for _ in range(2):
            assert invoke(SendEmail(), args, sink, ledger, attempts, naive=True).executed
        assert ledger.summary().attempts == 0
    assert len(sink.effects()) == 2
    assert attempts.count("send_email") == 2
