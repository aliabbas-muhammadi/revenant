import os

import pytest

from revenant.adapters.reference import ReferenceAdapter
from revenant.runner import ChildStatus, golden_run, kill_and_resume, stitch
from revenant.workloads import get_workload

posix = pytest.mark.skipif(os.name != "posix", reason="needs POSIX signals")


def test_stitch_plain_concatenation():
    assert stitch(["a", "b"], ["c", "d"], offset=2) == ("a", "b", "c", "d")


def test_stitch_overlap_prefers_post():
    assert stitch(["a", "b", "c"], ["b", "x"], offset=1) == ("a", "b", "x")


def test_stitch_full_replay():
    assert stitch(["a", "b"], ["a", "b", "c"]) == ("a", "b", "c")


def test_stitch_gap_is_kept_as_none():
    assert stitch(["a"], ["d"], offset=3) == ("a", None, None, "d")


def test_stitch_empty_and_negative():
    assert stitch([], []) == ()
    with pytest.raises(ValueError):
        stitch([], [], offset=-1)


@posix
def test_kill_then_resume_at_five_matches_golden(tmp_path):
    wl = get_workload("linear")
    golden = golden_run(ReferenceAdapter, wl, tmp_path / "g")
    res = kill_and_resume(ReferenceAdapter, wl, tmp_path / "k", 5)
    assert res.killed.status is ChildStatus.KILLED
    assert res.resumed.status is ChildStatus.COMPLETED
    assert res.boundary == 5
    assert res.stitched == golden.trace
