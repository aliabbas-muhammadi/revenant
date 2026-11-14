import pytest

from revenant.adapters.reference import CHECKPOINT_NAME, ReferenceAdapter
from revenant.chaos import flip_bit
from revenant.checkpoint import CheckpointError
from revenant.workloads import get_workload


def _resume_after_flip(tmp_path, offset, bit):
    a = ReferenceAdapter()
    a.build(get_workload("linear"), tmp_path)
    a._execute(stop_after=5)
    flip_bit(tmp_path / CHECKPOINT_NAME, offset, bit)
    b = ReferenceAdapter()
    b.build(get_workload("linear"), tmp_path)
    b.run()


@pytest.mark.parametrize("offset", [0, 10, 50, 120, -5, -1])
def test_reference_detects_a_flipped_bit(tmp_path, offset):
    with pytest.raises(CheckpointError):
        _resume_after_flip(tmp_path, offset, 0)


def test_flip_bit_changes_exactly_one_bit(tmp_path):
    path = tmp_path / "f"
    path.write_bytes(b"\x00\x00")
    flip_bit(path, 1, 3)
    assert path.read_bytes() == b"\x00\x08"
    flip_bit(path, -1, 3)
    assert path.read_bytes() == b"\x00\x00"


def test_langgraph_detects_a_damaged_header(tmp_path):
    pytest.importorskip("langgraph.checkpoint.sqlite")
    from revenant.adapters import langgraph_sqlite as lg

    saver = lg.open_checkpointer(tmp_path)
    lg.run_or_resume(lg.compile_graph(get_workload("linear"), tmp_path, saver, ["step_4"]))
    saver.conn.close()
    flip_bit(tmp_path / lg.CHECKPOINT_DB, 0)
    adapter = lg.LangGraphAdapter()
    adapter.build(get_workload("linear"), tmp_path)
    with pytest.raises(CheckpointError):
        adapter.run()
