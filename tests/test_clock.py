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
