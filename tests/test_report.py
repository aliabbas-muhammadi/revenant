from test_conformance import _b

from revenant.conformance import aggregate
from revenant.report import summary_line


def test_clean_pass_matches_the_design_line_exactly():
    r = aggregate("reference", "linear", [_b(k) for k in range(1, 13)])
    assert summary_line(r) == (
        "killed at 12/12 boundaries · resumes: 12/12 identical · effects: 3 once each"
        " · unconfirmed: 0 · verdict: PASS"
    )


def test_failures_are_surfaced_in_the_line():
    r = aggregate("a", "w", [_b(1, dup=["h"]), _b(2, ok=False, lost=[3])])
    line = summary_line(r)
    assert "resumes: 1/2 identical" in line
    assert "duplicated: 1" in line and "lost/phantom steps: 1" in line
    assert line.endswith("verdict: FAIL")


def test_planned_count_and_unconfirmed():
    r = aggregate("a", "w", [_b(1, unconf=["k"])])
    line = summary_line(r, planned=4)
    assert line.startswith("killed at 1/4 boundaries")
    assert "unconfirmed: 1" in line and line.endswith("PASS_WITH_UNCONFIRMED")


def test_markdown_has_one_row_per_boundary():
    from revenant.report import markdown_report

    r = aggregate("reference", "linear", [_b(1), _b(2, ok=False), _b(3, unconf=["k"])])
    md = markdown_report(r)
    lines = md.splitlines()
    assert lines[0] == "# reference · linear"
    rows = [ln for ln in lines if ln.startswith("| ") and not ln.startswith("| boundary")]
    assert len(rows) == 3
    assert rows[0] == "| 1 | boundary | identical | 3 | 0 | 0 | 0 | 0 | 0 | pass |"
    assert "diverged at step 3" in rows[1] and rows[1].endswith("| FAIL |")
    assert rows[2].count("| 1 |") >= 1
    assert md.endswith("\n")


def test_json_report_has_schema_and_versions():
    import json
    import sys

    from revenant import __version__
    from revenant.report import REPORT_SCHEMA_VERSION, json_report

    r = aggregate("reference", "linear", [_b(1), _b(2, unconf=["k"])])
    doc = json.loads(json_report(r))
    assert doc["schema_version"] == REPORT_SCHEMA_VERSION
    assert doc["versions"]["revenant"] == __version__
    assert doc["versions"]["python"] == sys.version.split()[0]
    assert set(doc["versions"]) == {"python", "revenant", "platform"}
    assert doc["verdict"] == "PASS_WITH_UNCONFIRMED"
    assert [b["boundary"] for b in doc["boundaries"]] == [1, 2]
    assert doc["boundaries"][1]["effects"]["unconfirmed"] == ["k"]


def test_json_report_is_stable_for_fixed_versions():
    from revenant.report import json_report

    r = aggregate("a", "w", [_b(1)])
    v = {"python": "3", "revenant": "0", "platform": "x"}
    assert json_report(r, versions=v) == json_report(r, versions=v)
    assert json_report(r, versions=v).endswith("}\n")


def test_markdown_from_dict_matches_markdown_report():
    from revenant.report import markdown_from_dict, markdown_report, report_dict

    results = (
        aggregate("reference", "linear", [_b(1), _b(2)]),
        aggregate("a", "w", [_b(1, ok=False), _b(2, unconf=["k"]), _b(3, dup=["h"], lost=[2])]),
    )
    for result in results:
        data = report_dict(result, versions={"python": "x"})
        assert markdown_from_dict(data) == markdown_report(result)


def test_langgraph_reports_carry_the_installed_langgraph_version():
    import json
    from importlib.metadata import version

    import pytest

    pytest.importorskip("langgraph")
    from revenant.report import json_report

    doc = json.loads(json_report(aggregate("langgraph_sqlite", "linear", [_b(1)])))
    assert doc["versions"]["langgraph"] == version("langgraph")
    assert doc["versions"]["langgraph-checkpoint-sqlite"] == version("langgraph-checkpoint-sqlite")


def test_other_adapters_do_not_list_langgraph():
    from revenant.report import versions_header

    assert "langgraph" not in versions_header("reference")
    assert "langgraph" not in versions_header()
