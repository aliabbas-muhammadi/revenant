from revenant.scoring import score_effects

A = {"tool": "send_email", "to": "a"}
B = {"tool": "charge_card", "amount_cents": 5}


def test_exactly_once_passes():
    s = score_effects([A, B], [B, A])
    assert s.passed and s.once == 2 and not s.unconfirmed


def test_duplicate_effect_fails():
    s = score_effects([A, B], [A, B, B])
    assert not s.passed and len(s.duplicated) == 1 and s.once == 1


def test_missing_effect_fails():
    s = score_effects([A, B], [A])
    assert not s.passed and len(s.missing) == 1


def test_unexpected_effect_fails():
    s = score_effects([A], [A, {"tool": "other"}])
    assert not s.passed and len(s.unexpected) == 1


def test_unconfirmed_is_reported_not_failed():
    s = score_effects([A], [A], unconfirmed=["k2", "k1"])
    assert s.passed and s.unconfirmed == ("k1", "k2")


def test_empty_golden_and_observed():
    assert score_effects([], []).passed
