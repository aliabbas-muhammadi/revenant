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


def test_start_is_read_only_and_survives_movement():
    clock = InjectedClock(4)
    clock.tick(3)
    assert clock.start == 4.0
    with pytest.raises(AttributeError):
        clock.start = 0.0  # type: ignore[misc]
    clock.reset()
    assert clock.start == 4.0


def test_until_counts_down_and_floors_at_zero():
    clock = InjectedClock(10)
    assert clock.until(15) == 5.0
    clock.tick(3)
    assert clock.until(15) == 2.0
    clock.tick(10)
    assert clock.until(15) == 0.0


def test_until_rejects_non_finite():
    clock = InjectedClock()
    for bad in (float("nan"), float("inf")):
        with pytest.raises(ValueError):
            clock.until(bad)


def test_has_reached_flips_at_the_boundary():
    clock = InjectedClock(10)
    assert not clock.has_reached(12)
    clock.tick(2)
    assert clock.has_reached(12)
    assert clock.has_reached(5)


def test_has_reached_rejects_non_finite():
    clock = InjectedClock()
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            clock.has_reached(bad)


def test_fork_is_independent():
    clock = InjectedClock(5)
    clock.tick(3)
    twin = clock.fork()
    assert twin.now() == 8.0 and twin.start == 5.0
    twin.tick(10)
    assert clock.now() == 8.0
    clock.reset()
    assert twin.now() == 18.0


def test_ticks_count_advances_and_reset_clears():
    clock = InjectedClock()
    assert clock.ticks == 0
    clock.tick(2)
    clock.advance_to(10)
    assert clock.ticks == 2
    clock.reset()
    assert clock.ticks == 0


def test_failed_advance_is_not_counted():
    clock = InjectedClock(5)
    with pytest.raises(ValueError):
        clock.tick(-1)
    with pytest.raises(ValueError):
        clock.advance_to(1)
    assert clock.ticks == 0


def test_fork_copies_ticks_independently():
    clock = InjectedClock()
    clock.tick()
    twin = clock.fork()
    twin.tick()
    assert (clock.ticks, twin.ticks) == (1, 2)


def test_tick_n_advances_and_counts_each_tick():
    clock = InjectedClock(10.0)
    assert clock.tick_n(3, 2.0) == 16.0
    assert clock.now() == 16.0
    assert clock.ticks == 3


def test_tick_n_default_is_one_second_steps():
    clock = InjectedClock()
    assert clock.tick_n(4) == 4.0


def test_tick_n_zero_is_a_noop():
    clock = InjectedClock(5.0)
    assert clock.tick_n(0) == 5.0
    assert clock.ticks == 0


def test_tick_n_rejects_bad_arguments_without_moving():
    clock = InjectedClock()
    for args in [(-1,), (1, -1.0), (1, float("nan")), (0, float("inf"))]:
        with pytest.raises(ValueError):
            clock.tick_n(*args)
    assert clock.now() == 0.0
    assert clock.ticks == 0


def test_span_is_positive_when_other_is_ahead():
    a, b = InjectedClock(0.0), InjectedClock(0.0)
    b.tick(5.0)
    assert a.span(b) == 5.0
    assert b.span(a) == -5.0


def test_span_of_a_clock_with_itself_and_its_fork_is_zero():
    clock = InjectedClock(3.0)
    assert clock.span(clock) == 0.0
    assert clock.span(clock.fork()) == 0.0


def test_span_uses_current_time_not_start():
    a, b = InjectedClock(10.0), InjectedClock(0.0)
    assert a.span(b) == -10.0
    b.advance_to(12.5)
    assert a.span(b) == 2.5


def test_is_ahead_of_compares_current_time():
    a, b = InjectedClock(0.0), InjectedClock(0.0)
    assert not a.is_ahead_of(b)
    a.tick(5.0)
    assert a.is_ahead_of(b)
    assert not b.is_ahead_of(a)


def test_is_ahead_of_a_clock_with_itself_or_its_fork_is_false():
    clock = InjectedClock(3.0)
    assert not clock.is_ahead_of(clock)
    assert not clock.is_ahead_of(clock.fork())


def test_is_ahead_of_agrees_with_span_sign():
    a, b = InjectedClock(0.0), InjectedClock(0.0)
    b.tick(4.0)
    assert a.is_ahead_of(b) == (a.span(b) < 0)
    assert b.is_ahead_of(a) == (b.span(a) < 0)
