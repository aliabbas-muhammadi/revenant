import pytest

from revenant.adapters.reference import LEDGER_NAME, ReferenceAdapter
from revenant.ledger import LedgerError, LedgerLost
from revenant.sink import EffectSink
from revenant.workloads import get_workload


def _killed_run(tmp_path):
    a = ReferenceAdapter()
    a.build(get_workload("linear"), tmp_path)
    a._execute(stop_after=5)


def test_deleted_ledger_is_detected_on_resume(tmp_path):
    _killed_run(tmp_path)
    before = len(EffectSink(tmp_path / "effects.jsonl").effects())
    for suffix in ("", "-wal", "-shm"):
        (tmp_path / (LEDGER_NAME + suffix)).unlink(missing_ok=True)
    b = ReferenceAdapter()
    b.build(get_workload("linear"), tmp_path)
    with pytest.raises(LedgerLost):
        b.run()
    assert len(EffectSink(tmp_path / "effects.jsonl").effects()) == before


def test_ledger_lost_is_a_ledger_error():
    assert issubclass(LedgerLost, LedgerError)


def test_fresh_workdir_does_not_trip_the_check(tmp_path):
    a = ReferenceAdapter()
    a.build(get_workload("linear"), tmp_path)
    assert a.run().completed
