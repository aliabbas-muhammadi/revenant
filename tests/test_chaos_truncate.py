import pytest

from revenant.adapters.reference import CHECKPOINT_NAME, ReferenceAdapter
from revenant.checkpoint import CheckpointCorrupt
from revenant.workloads import get_workload


def _partial(adapter, workdir):
    adapter.build(get_workload("linear"), workdir)
    adapter._execute(stop_after=5)


def test_reference_raises_on_truncated_checkpoint(tmp_path):
    _partial(ReferenceAdapter(), tmp_path)
    path = tmp_path / CHECKPOINT_NAME
    path.write_bytes(path.read_bytes()[:40])
    resumed = ReferenceAdapter()
    resumed.build(get_workload("linear"), tmp_path)
    with pytest.raises(CheckpointCorrupt):
        resumed.run()


def test_reference_raises_on_emptied_checkpoint(tmp_path):
    _partial(ReferenceAdapter(), tmp_path)
    (tmp_path / CHECKPOINT_NAME).write_bytes(b"")
    resumed = ReferenceAdapter()
    resumed.build(get_workload("linear"), tmp_path)
    with pytest.raises(CheckpointCorrupt):
        resumed.run()


def test_langgraph_raises_on_truncated_database(tmp_path):
    pytest.importorskip("langgraph.checkpoint.sqlite")
    from revenant.adapters import langgraph_sqlite as lg

    saver = lg.open_checkpointer(tmp_path)
    graph = lg.compile_graph(get_workload("linear"), tmp_path, saver, ["step_4"])
    lg.run_or_resume(graph)
    saver.conn.close()
    path = tmp_path / lg.CHECKPOINT_DB
    path.write_bytes(path.read_bytes()[:100])
    resumed = lg.LangGraphAdapter()
    resumed.build(get_workload("linear"), tmp_path)
    with pytest.raises(CheckpointCorrupt):
        resumed.run()


def test_langgraph_raises_on_emptied_database(tmp_path):
    pytest.importorskip("langgraph.checkpoint.sqlite")
    from revenant.adapters import langgraph_sqlite as lg

    saver = lg.open_checkpointer(tmp_path)
    graph = lg.compile_graph(get_workload("linear"), tmp_path, saver, ["step_4"])
    lg.run_or_resume(graph)
    saver.conn.close()
    (tmp_path / lg.CHECKPOINT_DB).write_bytes(b"")
    adapter = lg.LangGraphAdapter()
    adapter.build(get_workload("linear"), tmp_path)
    with pytest.raises(CheckpointCorrupt):
        adapter.run()
