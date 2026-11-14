import os

import pytest

pytest.importorskip("langgraph.checkpoint.sqlite")

from revenant.adapters import langgraph_sqlite as lg  # noqa: E402
from revenant.adapters.reference import ReferenceAdapter  # noqa: E402
from revenant.cli import main  # noqa: E402
from revenant.sink import EffectSink  # noqa: E402
from revenant.workloads import get_workload  # noqa: E402

posix = pytest.mark.skipif(os.name != "posix", reason="needs POSIX signals")


def test_parallel_branches_share_one_superstep(tmp_path):
    wl = get_workload("fanout")
    a = lg.LangGraphAdapter()
    a.build(wl, tmp_path)
    result = a.run()
    assert a.boundaries() == 3
    assert len(result.trace) == 3
    assert len(list(EffectSink(tmp_path / "effects.jsonl").effects())) == 3


def test_final_hash_matches_the_reference(tmp_path):
    wl = get_workload("fanout")
    a = lg.LangGraphAdapter()
    a.build(wl, tmp_path / "lg")
    ref = ReferenceAdapter()
    ref.build(wl, tmp_path / "ref")
    assert a.run().final_hash == ref.run().final_hash


@posix
def test_sweep_passes_with_ledgered_tools(capsys):
    args = ["run", "--adapter", "langgraph_sqlite", "--workload", "fanout"]
    assert main(args) == 0
    out = capsys.readouterr().out
    assert "killed at 3/3 boundaries" in out and "duplicated" not in out


@posix
def test_naive_mid_kill_duplicates_sibling_effects(capsys):
    args = ["run", "--adapter", "langgraph_sqlite", "--workload", "fanout",
            "--mode", "mid", "--naive-tools"]  # fmt: skip
    assert main(args) == 1
    assert "duplicated" in capsys.readouterr().out
