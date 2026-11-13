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
