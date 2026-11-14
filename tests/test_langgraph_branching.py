from dataclasses import replace

import pytest

pytest.importorskip("langgraph.graph")

from revenant.adapters.langgraph_sqlite import build_graph, initial_state  # noqa: E402
from revenant.adapters.reference import ReferenceAdapter  # noqa: E402
from revenant.canon import state_hash  # noqa: E402
from revenant.sink import EffectSink  # noqa: E402
from revenant.workloads import get_workload  # noqa: E402


def test_branching_graph_matches_the_reference_final_hash(tmp_path):
    wl = get_workload("branching")
    final = build_graph(wl, tmp_path / "lg").compile().invoke(initial_state())
    assert final["step"] == 10
    ref = ReferenceAdapter()
    ref.build(wl, tmp_path / "ref")
    assert state_hash(dict(final), wl.volatile_fields) == ref.run().final_hash
    assert len(list(EffectSink(tmp_path / "lg" / "effects.jsonl").effects())) == 9


def test_every_node_has_a_conditional_edge():
    graph = build_graph(get_workload("branching"), "unused-dir")
    assert set(graph.branches) == set(graph.nodes)


def test_stop_response_ends_the_run_early(tmp_path):
    wl = get_workload("branching")
    script = list(wl.script)
    script[3] = {"action": "stop"}
    short = replace(wl, script=tuple(script))
    final = build_graph(short, tmp_path).compile().invoke(initial_state())
    assert final["step"] == 4
    assert len(list(EffectSink(tmp_path / "effects.jsonl").effects())) == 4
