from revenant.adapters.reference import ReferenceAdapter
from revenant.sink import EffectSink
from revenant.workloads import get_workload


class DupAdapter(ReferenceAdapter):
    duplicate_delivery = True


class NaiveDupAdapter(DupAdapter):
    naive_tools = True


def _run(cls, tmp_path):
    a = cls()
    a.build(get_workload("linear"), tmp_path)
    result = a.run()
    return result, list(EffectSink(tmp_path / "effects.jsonl").effects())


def test_ledger_absorbs_duplicate_delivery(tmp_path):
    result, effects = _run(DupAdapter, tmp_path)
    assert result.completed
    assert len(effects) == 3


def test_duplicate_delivery_does_not_change_the_trace(tmp_path):
    plain, _ = _run(ReferenceAdapter, tmp_path / "a")
    dup, _ = _run(DupAdapter, tmp_path / "b")
    assert plain.trace == dup.trace


def test_naive_tools_perform_every_delivery(tmp_path):
    _, effects = _run(NaiveDupAdapter, tmp_path)
    assert len(effects) == 6
