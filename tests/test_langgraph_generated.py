"""LangGraph with ledgered tools on a generated linear-style workload."""

import os

import pytest

pytest.importorskip("langgraph.graph")

from revenant.cli import main  # noqa: E402

pytestmark = pytest.mark.skipif(os.name != "posix", reason="needs POSIX signals")


def test_ledgered_tools_pass_on_generated_workload(capsys):
    code = main(["run", "--adapter", "langgraph_sqlite", "--workload", "gen-1",
                 "--mode", "mid", "--jobs", "4"])  # fmt: skip
    assert code == 0
    assert "verdict: PASS" in capsys.readouterr().out
