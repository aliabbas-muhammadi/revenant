from revenant.adapters.reference import ReferenceAdapter
from revenant.ledger import Ledger
from revenant.sink import EffectSink
from revenant.workloads import get_workload


class TimeoutAdapter(ReferenceAdapter):
    timeout_retry = True


def test_retry_after_a_hung_attempt_lands_each_effect_once(tmp_path):
    a = TimeoutAdapter()
    a.build(get_workload("linear"), tmp_path)
    assert a.run().completed
    assert len(list(EffectSink(tmp_path / "effects.jsonl").effects())) == 3
    with Ledger(tmp_path / "ledger.db") as ledger:
        summary = ledger.summary()
        assert summary.effects == 3 and summary.unconfirmed == 0
        assert summary.attempts == 6


def test_timeout_retry_leaves_the_trace_unchanged(tmp_path):
    plain = ReferenceAdapter()
    plain.build(get_workload("linear"), tmp_path / "a")
    chaos = TimeoutAdapter()
    chaos.build(get_workload("linear"), tmp_path / "b")
    assert plain.run().trace == chaos.run().trace
