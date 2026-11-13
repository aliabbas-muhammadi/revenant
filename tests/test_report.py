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
