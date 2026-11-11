import pytest

from revenant.ledger import Ledger
from revenant.sink import EffectSink
from revenant.tools import ChargeCard, ToolError, invoke

ARGS = {"customer": "cus_1", "amount_cents": 1999}


def test_perform_records_charge(tmp_path):
    sink = EffectSink(tmp_path / "s.jsonl")
    assert ChargeCard().perform(ARGS, sink) == "charged"
    assert sink.effects() == [{"tool": "charge_card", **ARGS}]


def test_key_depends_on_customer_and_amount():
    tool = ChargeCard()
    key = tool.idempotency_key(ARGS)
    assert key.startswith("charge_card:")
    assert key != tool.idempotency_key({**ARGS, "amount_cents": 2000})
    assert key != tool.idempotency_key({**ARGS, "customer": "cus_2"})


@pytest.mark.parametrize("amount", [0, -5, 1.5, 10.0, "100", None, True], ids=repr)
def test_bad_amounts_rejected(amount):
    with pytest.raises(ToolError, match="amount_cents"):
        ChargeCard().idempotency_key({**ARGS, "amount_cents": amount})


@pytest.mark.parametrize(
    "bad", [{"amount_cents": 5}, {"customer": "c"}, {"customer": "", "amount_cents": 5}]
)
def test_missing_or_empty_fields_rejected(bad):
    with pytest.raises(ToolError):
        ChargeCard().idempotency_key(bad)


def test_ledgered_repeat_charges_once(tmp_path):
    sink = EffectSink(tmp_path / "s.jsonl")
    with Ledger(tmp_path / "l.db") as ledger:
        for _ in range(3):
            invoke(ChargeCard(), ARGS, sink, ledger)
    assert len(sink.effects()) == 1
