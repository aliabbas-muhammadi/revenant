from revenant.scoring import score_determinism

G = ["h1", "h2", "h3", "h4"]


def test_identical_trace_passes():
    s = score_determinism(G, list(G), 2)
    assert s.passed and s.first_divergent_step is None and s.final_state_matches


def test_divergent_hash_after_boundary_is_reported():
    s = score_determinism(G, ["h1", "h2", "X", "h4"], 2)
    assert not s.passed
    assert s.first_divergent_step == 3
    assert "step 3" in s.detail


def test_divergence_before_boundary_is_not_property_one():
    assert score_determinism(G, ["X", "h2", "h3", "h4"], 2).passed


def test_divergent_final_state_with_matching_steps_after_boundary():
    # Boundary at the very end: nothing to compare per step, final still checked.
    s = score_determinism(G, ["h1", "h2", "h3", "Z"], 4)
    assert not s.passed and not s.final_state_matches
    assert s.first_divergent_step is None


def test_missing_steps_count_as_divergence():
    s = score_determinism(G, ["h1", "h2", None, None], 2)
    assert not s.passed and s.first_divergent_step == 3


def test_empty_stitched_fails():
    assert not score_determinism(G, [], 0).passed
