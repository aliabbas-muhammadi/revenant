import os

import pytest

from revenant.adapters.reference import ReferenceAdapter
from revenant.report import report_dict
from revenant.runner import sweep, tool_breakdown
from revenant.workloads import get_workload

posix = pytest.mark.skipif(os.name != "posix", reason="needs POSIX signals")


def test_empty_workdir_has_no_breakdown(tmp_path):
    assert tool_breakdown(tmp_path) == {}


def test_golden_run_counts_attempts_and_effects(tmp_path):
    adapter = ReferenceAdapter()
    adapter.build(get_workload("linear"), tmp_path)
    adapter.run()
    breakdown = tool_breakdown(tmp_path)
    assert breakdown
    for counts in breakdown.values():
        assert counts["attempts"] == counts["effects"] >= 1


@posix
def test_swept_boundary_reports_tool_counts(tmp_path):
    res = sweep(
        ReferenceAdapter, get_workload("linear"), tmp_path, mode="mid", boundaries=[2]
    )
    (boundary,) = res.boundaries
    assert boundary.tools
    assert sum(c["effects"] or 0 for c in boundary.tools.values()) == boundary.effects.once
    data = report_dict(res)
    assert data["boundaries"][0]["tools"] == boundary.tools  # type: ignore[index]


def test_histogram_empty_without_ledger(tmp_path):
    from revenant.runner import attempt_histogram

    assert attempt_histogram(tmp_path) == {}


def test_ledger_histogram_groups_by_attempts(tmp_path):
    from revenant.ledger import Ledger

    with Ledger(tmp_path / "l.db") as ledger:
        for key, attempts in (("a:1", 1), ("a:2", 3), ("b:1", 3)):
            ledger.begin(key, {"k": key})
            ledger.commit(key)
            for _ in range(attempts - 1):
                ledger.begin(key, {"k": key})
        assert ledger.attempt_histogram() == {1: 1, 3: 2}


def test_markdown_renders_histogram():
    from revenant.report import markdown_from_dict

    data = {
        "adapter": "x", "workload": "w", "summary": "s",
        "boundaries": [
            {"boundary": 1, "mode": "mid", "passed": True, "attempt_histogram": {"1": 2, "2": 1},
             "determinism": {"passed": True, "first_divergent_step": None},
             "effects": {"once": 3, "duplicated": [], "missing": [], "unconfirmed": []},
             "steps": {"lost": [], "phantom": []}},
            {"boundary": 2, "mode": "mid", "passed": True, "attempt_histogram": {"1": 1},
             "determinism": {"passed": True, "first_divergent_step": None},
             "effects": {"once": 3, "duplicated": [], "missing": [], "unconfirmed": []},
             "steps": {"lost": [], "phantom": []}},
        ],
    }
    text = markdown_from_dict(data)
    assert "## Attempts per effect" in text
    assert "| 1 | 3 |" in text and "| 2 | 1 |" in text
