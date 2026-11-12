from revenant.conformance import BoundaryResult, ConformanceResult, aggregate
from revenant.scoring import DeterminismScore, EffectsScore, StepsScore


def _b(k, ok=True, dup=(), unconf=(), lost=(), once=3):
    return BoundaryResult(
        k, "boundary",
        DeterminismScore(ok, None if ok else k + 1),
        EffectsScore(once, tuple(dup), (), (), tuple(unconf)),
        StepsScore(tuple(lost), ()),
    )  # fmt: skip


def test_all_green_boundaries_pass():
    r = aggregate("reference", "linear", [_b(1), _b(2)])
    assert r.passed and r.total == 2 and r.identical_resumes == 2
    assert r.failing() == () and r.effects_once == 3


def test_divergence_is_counted_and_listed():
    r = aggregate("reference", "linear", [_b(1), _b(2, ok=False)])
    assert not r.passed and r.identical_resumes == 1 and r.failing() == (2,)


def test_duplicates_and_lost_steps_fail_the_boundary():
    r = aggregate("a", "w", [_b(1, dup=["h"]), _b(2, lost=[4, 5])])
    assert r.duplicated == 1 and r.lost_or_phantom == 2 and r.failing() == (1, 2)


def test_unconfirmed_is_reported_but_does_not_fail():
    r = aggregate("a", "w", [_b(1, unconf=["k"])])
    assert r.unconfirmed == 1 and r.passed


def test_aggregate_sorts_boundaries():
    r = aggregate("a", "w", [_b(3), _b(1), _b(2)])
    assert [b.boundary for b in r.boundaries] == [1, 2, 3]


def test_empty_result_is_vacuously_passing_with_zero_totals():
    r = ConformanceResult("a", "w", ())
    assert r.total == 0 and r.effects_once == 0
