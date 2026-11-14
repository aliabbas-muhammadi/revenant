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
