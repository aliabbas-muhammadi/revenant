import pytest

pytest.importorskip("langgraph.checkpoint.sqlite")

from revenant.adapters import langgraph_sqlite as lg  # noqa: E402
from revenant.sink import EffectSink  # noqa: E402
from revenant.workloads import get_workload  # noqa: E402


class Died(Exception):
    pass


def _boom():
    raise Died


def _run(tmp_path, kill_at=None, kill_mid=False):
    saver = lg.open_checkpointer(tmp_path)
    try:
        graph = lg.compile_graph(
            get_workload("linear"), tmp_path, saver, kill_at=kill_at, kill_mid=kill_mid
        )
        return lg.run_or_resume(graph)
    finally:
        saver.conn.close()


def _effects(tmp_path):
    return len(list(EffectSink(tmp_path / "effects.jsonl").effects()))


def test_boundary_kill_leaves_k_supersteps_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(lg, "die", _boom)
    with pytest.raises(Died):
        _run(tmp_path, kill_at=5)
    saver = lg.open_checkpointer(tmp_path)
    graph = lg.compile_graph(get_workload("linear"), tmp_path, saver)
    assert graph.get_state(lg.thread_config()).values["step"] == 5
    saver.conn.close()


def test_boundary_kill_then_resume_finishes(tmp_path, monkeypatch):
    monkeypatch.setattr(lg, "die", _boom)
    with pytest.raises(Died):
        _run(tmp_path, kill_at=3)
    assert _run(tmp_path)["step"] == 12


def test_mid_kill_loses_the_superstep_but_not_the_effect(tmp_path, monkeypatch):
    monkeypatch.setattr(lg, "die", _boom)
    # find a step that has a tool call
    wl = get_workload("linear")
    k = next(i for i, s in enumerate(wl.steps, 1) if s.tool is not None)
    with pytest.raises(Died):
        _run(tmp_path, kill_at=k, kill_mid=True)
    assert _effects(tmp_path) == 1
    saver = lg.open_checkpointer(tmp_path)
    graph = lg.compile_graph(wl, tmp_path, saver)
    assert graph.get_state(lg.thread_config()).values["step"] == k - 1
    saver.conn.close()
