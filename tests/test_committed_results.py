import json
from pathlib import Path

import pytest

from revenant.cli import main
from revenant.report import REPORT_SCHEMA_VERSION, markdown_from_dict
from revenant.workloads import WORKLOAD_NAMES

RESULTS = Path(__file__).resolve().parent.parent / "results"


@pytest.mark.parametrize("workload", WORKLOAD_NAMES)
def test_committed_reference_results_are_consistent(workload, capsys):
    json_path = RESULTS / f"reference-{workload}.json"
    data = json.loads(json_path.read_text())
    assert data["schema_version"] == REPORT_SCHEMA_VERSION
    assert data["verdict"] == "PASS"
    assert set(data["versions"]) == {"python", "revenant", "platform"}
    assert (RESULTS / f"reference-{workload}.md").read_text() == markdown_from_dict(data)
    assert main(["report", str(json_path)]) == 0
    assert capsys.readouterr().out.strip() == data["summary"]


MUTANTS = sorted(p.name[: -len(".json")] for p in (RESULTS / "mutants").glob("*.json"))


def test_every_mutant_has_a_committed_result():
    assert len(MUTANTS) == 5


@pytest.mark.parametrize("name", MUTANTS)
def test_committed_mutant_results_fail_and_match_markdown(name):
    data = json.loads((RESULTS / "mutants" / f"{name}.json").read_text())
    assert data["schema_version"] == REPORT_SCHEMA_VERSION
    assert data["verdict"] == "FAIL"
    assert (RESULTS / "mutants" / f"{name}.md").read_text() == markdown_from_dict(data)


LANGGRAPH = sorted(p.name[: -len(".json")] for p in (RESULTS / "langgraph").glob("*.json"))


def test_langgraph_results_cover_both_tool_modes_for_every_workload():
    assert LANGGRAPH == sorted(f"{m}-{w}" for m in ("ledgered", "naive") for w in WORKLOAD_NAMES)


@pytest.mark.parametrize("name", LANGGRAPH)
def test_committed_langgraph_results_match_markdown_and_name_langgraph(name):
    data = json.loads((RESULTS / "langgraph" / f"{name}.json").read_text())
    assert data["adapter"] == "langgraph_sqlite"
    assert data["schema_version"] == REPORT_SCHEMA_VERSION
    assert {"langgraph", "langgraph-checkpoint-sqlite"} <= set(data["versions"])
    assert (RESULTS / "langgraph" / f"{name}.md").read_text() == markdown_from_dict(data)


@pytest.mark.parametrize("workload", WORKLOAD_NAMES)
def test_committed_naive_langgraph_runs_duplicate_effects(workload):
    data = json.loads((RESULTS / "langgraph" / f"naive-{workload}.json").read_text())
    assert data["verdict"] == "FAIL"
    assert any(b["effects"]["duplicated"] for b in data["boundaries"])


CHAOS_MODES_COMMITTED = ("dup", "timeout", "corrupt", "all")


@pytest.mark.parametrize("workload", WORKLOAD_NAMES)
@pytest.mark.parametrize("mode", CHAOS_MODES_COMMITTED)
def test_committed_chaos_results_pass_and_match_markdown(workload, mode):
    stem = RESULTS / "chaos" / f"reference-{workload}-{mode}"
    data = json.loads(stem.with_suffix(".json").read_text())
    assert data["chaos"] == mode
    assert data["verdict"] == "PASS"
    assert stem.with_suffix(".md").read_text() == markdown_from_dict(data)
    if mode in ("corrupt", "all"):
        assert all(b["detected"] is True for b in data["boundaries"])
