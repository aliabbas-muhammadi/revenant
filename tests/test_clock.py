import pytest

from revenant.clock import InjectedClock


def test_now_is_stable_until_tick():
    clock = InjectedClock(100)
    assert clock.now() == clock.now() == 100.0


def test_tick_advances():
    clock = InjectedClock()
    assert clock.tick() == 1.0
    assert clock.tick(2.5) == 3.5
    assert clock.now() == 3.5


def test_tick_rejects_negative():
    with pytest.raises(ValueError):
        InjectedClock().tick(-1)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_tick_rejects_non_finite(bad):
    with pytest.raises(ValueError):
        InjectedClock().tick(bad)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_start_rejects_non_finite(bad):
    with pytest.raises(ValueError):
        InjectedClock(bad)


def test_elapsed_counts_from_start():
    clock = InjectedClock(100)
    assert clock.elapsed() == 0.0
    clock.tick(2.5)
    assert clock.elapsed() == 2.5


def test_repr_shows_current_time():
    clock = InjectedClock(3)
    clock.tick()
    assert repr(clock) == "InjectedClock(now=4.0)"


def test_advance_to_moves_to_absolute_time():
    clock = InjectedClock(10)
    assert clock.advance_to(12.5) == 12.5
    assert clock.now() == 12.5
    assert clock.advance_to(12.5) == 12.5


@pytest.mark.parametrize("bad", [9, float("nan"), float("inf")])
def test_advance_to_rejects_past_and_non_finite(bad):
    clock = InjectedClock(10)
    with pytest.raises(ValueError):
        clock.advance_to(bad)
    assert clock.now() == 10.0


def test_reset_returns_to_start():
    clock = InjectedClock(5)
    clock.tick(7)
    clock.reset()
    assert clock.now() == 5.0
    assert clock.elapsed() == 0.0


def test_is_at_start_tracks_movement():
    clock = InjectedClock(3)
    assert clock.is_at_start()
    clock.tick(0)
    assert clock.is_at_start()
    clock.tick(1)
    assert not clock.is_at_start()
    clock.reset()
    assert clock.is_at_start()
