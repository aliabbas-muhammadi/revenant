import pytest

from revenant.result import RunResult


def test_final_hash_is_last_trace_entry():
    r = RunResult(completed=True, steps_run=2, trace=("a", "b"))
    assert r.final_hash == "b"


def test_empty_trace_has_no_final_hash():
    assert RunResult(False, 0, ()).final_hash is None


def test_steps_run_cannot_exceed_trace():
    with pytest.raises(ValueError):
        RunResult(True, 3, ("a",))


def test_negative_steps_rejected():
    with pytest.raises(ValueError):
        RunResult(False, -1, ())
