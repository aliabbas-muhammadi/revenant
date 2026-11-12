from revenant.scoring import score_steps

G = ["h1", "h2", "h3"]


def test_complete_trace_passes():
    s = score_steps(G, list(G))
    assert s.passed and not s.lost and not s.phantom


def test_gap_is_a_lost_step():
    assert score_steps(G, ["h1", None, "h3"]).lost == (2,)


def test_truncated_trace_loses_trailing_steps():
    s = score_steps(G, ["h1"])
    assert s.lost == (2, 3) and not s.passed


def test_extra_steps_are_phantom():
    s = score_steps(G, ["h1", "h2", "h3", "h4", "h5"])
    assert s.phantom == (4, 5) and not s.passed


def test_wrong_hash_is_not_lost():
    assert score_steps(G, ["h1", "X", "h3"]).passed


def test_empty_stitched_loses_everything():
    assert score_steps(G, []).lost == (1, 2, 3)
