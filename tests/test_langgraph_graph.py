import pytest

pytest.importorskip("langgraph.graph")

from revenant.adapters.langgraph_sqlite import build_graph, initial_state  # noqa: E402
from revenant.adapters.reference import ReferenceAdapter  # noqa: E402
from revenant.canon import state_hash  # noqa: E402
from revenant.sink import EffectSink  # noqa: E402
from revenant.workloads import get_workload  # noqa: E402


def test_linear_graph_has_one_node_per_step(tmp_path):
    wl = get_workload("linear")
    graph = build_graph(wl, tmp_path)
    assert [n for n in graph.nodes] == [f"step_{i}" for i in range(12)]


def test_linear_graph_matches_the_reference_final_hash(tmp_path):
    wl = get_workload("linear")
    final = build_graph(wl, tmp_path / "lg").compile().invoke(initial_state())
    assert final["step"] == 12
    ref = ReferenceAdapter()
    ref.build(wl, tmp_path / "ref")
    expected = ref.run().final_hash
    assert state_hash(dict(final), wl.volatile_fields) == expected
    assert len(list(EffectSink(tmp_path / "lg" / "effects.jsonl").effects())) == 3
