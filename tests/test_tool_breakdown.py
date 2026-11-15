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
