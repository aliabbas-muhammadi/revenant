import os

import pytest

pytest.importorskip("langgraph.checkpoint.sqlite")

from revenant.cli import main  # noqa: E402

posix = pytest.mark.skipif(os.name != "posix", reason="needs POSIX signals")
BASE = ["run", "--adapter", "langgraph_sqlite", "--workload", "linear", "--mode", "mid"]


@posix
def test_ledgered_tools_are_the_default(capsys):
    assert main([*BASE, "--kill-at", "3"]) == 0
    out = capsys.readouterr().out
    assert "effects: 3 once each" in out and "duplicated" not in out


@posix
def test_naive_tools_duplicate_the_effect_of_the_killed_node(capsys):
    assert main([*BASE, "--kill-at", "3", "--naive-tools"]) == 1
    assert "duplicated: 1" in capsys.readouterr().out


def test_naive_tools_flag_is_rejected_for_other_adapters(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["run", "--adapter", "reference", "--workload", "linear", "--naive-tools"])
    assert exc.value.code == 2
    assert "langgraph_sqlite" in capsys.readouterr().err


def test_adapter_defaults_to_ledgered():
    from revenant.adapters.langgraph_sqlite import LangGraphAdapter

    assert LangGraphAdapter().naive_tools is False
