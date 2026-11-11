import pytest

from revenant.ledger import Ledger
from revenant.sink import EffectSink
from revenant.tools import SendEmail, ToolError, invoke

ARGS = {"to": "a@example.com", "subject": "Hi", "body": "Hello"}


def test_key_is_stable_and_depends_on_content():
    tool = SendEmail()
    assert tool.idempotency_key(ARGS) == tool.idempotency_key(dict(reversed(ARGS.items())))
    assert tool.idempotency_key(ARGS) != tool.idempotency_key({**ARGS, "body": "Other"})
    assert tool.idempotency_key(ARGS).startswith("send_email:")


def test_perform_writes_one_sink_record(tmp_path):
    sink = EffectSink(tmp_path / "s.jsonl")
    SendEmail().perform(ARGS, sink)
    assert sink.effects() == [{"tool": "send_email", **ARGS}]


def test_ledgered_repeat_sends_once(tmp_path):
    sink = EffectSink(tmp_path / "s.jsonl")
    with Ledger(tmp_path / "l.db") as ledger:
        invoke(SendEmail(), ARGS, sink, ledger)
        invoke(SendEmail(), ARGS, sink, ledger)
    assert len(sink.effects()) == 1


@pytest.mark.parametrize("bad", [{"to": "a"}, {**ARGS, "body": 3}])
def test_invalid_args_raise(bad):
    with pytest.raises(ToolError):
        SendEmail().idempotency_key(bad)
