import os

import pytest

pytest.importorskip("langgraph.checkpoint.sqlite")

from revenant.cli import main  # noqa: E402

posix = pytest.mark.skipif(os.name != "posix", reason="needs POSIX signals")
BASE = ["run", "--adapter", "langgraph_sqlite", "--workload", "linear"]


@posix
@pytest.mark.parametrize("mode", ["boundary", "mid"])
def test_ledgered_linear_sweep_passes_with_every_effect_once(capsys, mode):
    assert main([*BASE, "--mode", mode]) == 0
    out = capsys.readouterr().out
    assert "effects: 3 once each" in out
    assert "duplicated" not in out and "missing" not in out


@posix
def test_naive_tools_record_duplicate_effects_in_the_mid_step_sweep(tmp_path):
    """Measurement, not a pass: the naive runtime must show duplicates."""
    import functools
    import sys

    from revenant.adapters.langgraph_sqlite import LangGraphAdapter
    from revenant.runner import sweep
    from revenant.workloads import get_workload

    def argv_for(workdir):
        return [sys.executable, "-m", "revenant.adapters.langgraph_sqlite",
                "--workload", "linear", "--workdir", str(workdir), "--naive-tools"]  # fmt: skip

    res = sweep(
        functools.partial(LangGraphAdapter, naive_tools=True),
        get_workload("linear"), tmp_path, mode="mid", argv_for=argv_for,
    )  # fmt: skip
    duplicated = sum(len(b.effects.duplicated) for b in res.boundaries)
    assert duplicated > 0
    assert not res.passed
