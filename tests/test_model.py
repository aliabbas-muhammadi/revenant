import pytest

from revenant.canon import state_hash
from revenant.model import PromptDivergence, ScriptedModel, ScriptExhausted


def test_returns_response_by_index():
    model = ScriptedModel(["a", {"tool": "x"}])
    assert model.respond(1) == {"tool": "x"}
    assert model.respond(0) == "a"
    assert len(model) == 2


def test_same_step_same_answer():
    model = ScriptedModel(["a", "b"])
    assert model.respond(1) == model.respond(1)


@pytest.mark.parametrize("step", [2, -1])
def test_out_of_range_raises(step):
    with pytest.raises(ScriptExhausted):
        ScriptedModel(["a", "b"]).respond(step)


def test_matching_prompt_passes():
    prompt = {"q": "hi"}
    model = ScriptedModel(["a", "b"], [state_hash(prompt), None])
    assert model.respond(0, prompt) == "a"


def test_mismatched_prompt_raises():
    model = ScriptedModel(["a"], [state_hash({"q": "hi"})])
    with pytest.raises(PromptDivergence, match="step 0"):
        model.respond(0, {"q": "changed"})


def test_unpinned_step_and_missing_prompt_are_not_checked():
    model = ScriptedModel(["a", "b"], [None, state_hash("x")])
    assert model.respond(0, "anything") == "a"
    assert model.respond(1) == "b"


def test_prompt_hashes_length_validated():
    with pytest.raises(ValueError):
        ScriptedModel(["a", "b"], [None])


def test_remaining_counts_responses_left():
    model = ScriptedModel(["a", "b", "c"])
    assert model.remaining(0) == 3
    assert model.remaining(2) == 1
    assert model.remaining(3) == 0
    assert model.remaining(99) == 0


def test_divergence_message_shows_short_hashes():
    model = ScriptedModel(["a"], prompt_hashes=[state_hash("expected")])
    with pytest.raises(PromptDivergence) as err:
        model.respond(0, "other")
    assert str(err.value) == (
        f"step 0: prompt hash {state_hash('other')[:12]} != expected {state_hash('expected')[:12]}"
    )


def test_repr_shows_length_and_pinning():
    assert repr(ScriptedModel(["a", "b"])) == "ScriptedModel(responses=2, prompts_pinned=False)"
    pinned = ScriptedModel(["a"], prompt_hashes=[None])
    assert repr(pinned) == "ScriptedModel(responses=1, prompts_pinned=True)"


def test_is_exhausted_past_the_end():
    model = ScriptedModel(["a", "b"])
    assert not model.is_exhausted(0)
    assert not model.is_exhausted(1)
    assert model.is_exhausted(2)
    assert model.is_exhausted(10)
    assert ScriptedModel([]).is_exhausted(0)


def test_responses_returns_a_copy():
    model = ScriptedModel(["a", "b"])
    out = model.responses()
    assert out == ["a", "b"]
    out.append("c")
    assert model.responses() == ["a", "b"]
    assert ScriptedModel([]).responses() == []


def test_iteration_yields_responses_in_order():
    model = ScriptedModel(["a", "b", "c"])
    assert list(model) == ["a", "b", "c"]
    assert list(model) == ["a", "b", "c"]
    assert list(ScriptedModel([])) == []


def test_peek_returns_response_without_prompt_check():
    model = ScriptedModel(["a", "b"], prompt_hashes=[state_hash("x"), None])
    assert model.peek(0) == "a"
    assert model.peek(1) == "b"


@pytest.mark.parametrize("step", [-1, 2])
def test_peek_out_of_range_raises(step):
    with pytest.raises(ScriptExhausted):
        ScriptedModel(["a", "b"]).peek(step)


def test_window_returns_clamped_slice():
    model = ScriptedModel(["a", "b", "c", "d"])
    assert model.window(1, 3) == ["b", "c"]
    assert model.window(2, 99) == ["c", "d"]
    assert model.window(3, 1) == []
    assert model.window(0, 0) == []


def test_window_is_a_copy_and_rejects_negatives():
    model = ScriptedModel(["a", "b"])
    model.window(0, 2).append("x")
    assert model.responses() == ["a", "b"]
    with pytest.raises(ValueError):
        model.window(-1, 2)
    with pytest.raises(ValueError):
        model.window(0, -1)


def test_is_pinned_reports_per_step_prompt_pins():
    pin = state_hash("p")
    model = ScriptedModel(["a", "b", "c"], prompt_hashes=[pin, None, pin])
    assert [model.is_pinned(i) for i in range(3)] == [True, False, True]


def test_is_pinned_is_false_without_pins_or_out_of_range():
    assert not ScriptedModel(["a"]).is_pinned(0)
    model = ScriptedModel(["a"], prompt_hashes=[state_hash("p")])
    assert not model.is_pinned(1)
    assert not model.is_pinned(-1)


def test_find_returns_first_matching_step():
    model = ScriptedModel(["a", {"tool": "x"}, "a"])
    assert model.find("a") == 0
    assert model.find({"tool": "x"}) == 1
    assert model.find("missing") is None
    assert ScriptedModel([]).find("a") is None


def test_last_step_is_final_index():
    model = ScriptedModel(["a", "b", "c"])
    assert model.last_step() == 2
    assert model.respond(model.last_step()) == "c"


def test_last_step_none_when_empty():
    assert ScriptedModel([]).last_step() is None


def test_count_matches_equal_responses():
    model = ScriptedModel(["a", "b", "a", {"x": 1}, {"x": 1}])
    assert model.count("a") == 2
    assert model.count({"x": 1}) == 2
    assert model.count("missing") == 0


def test_count_empty_script():
    assert ScriptedModel([]).count("a") == 0


def test_indices_of_lists_every_matching_step():
    model = ScriptedModel(["a", "b", "a", "c", "a"])
    assert model.indices_of("a") == [0, 2, 4]
    assert model.indices_of("c") == [3]


def test_indices_of_missing_response_is_empty():
    assert ScriptedModel(["a"]).indices_of("z") == []
    assert ScriptedModel([]).indices_of("a") == []


def test_indices_of_agrees_with_find_and_count():
    model = ScriptedModel([{"x": 1}, {"x": 2}, {"x": 1}])
    hits = model.indices_of({"x": 1})
    assert hits[0] == model.find({"x": 1})
    assert len(hits) == model.count({"x": 1})


def test_distinct_count_counts_unique_responses():
    assert ScriptedModel(["a", "b", "a", "c", "b"]).distinct_count() == 3


def test_distinct_count_handles_unhashable_and_key_order():
    model = ScriptedModel([{"a": 1, "b": 2}, {"b": 2, "a": 1}, [1, 2], [1, 2], [2, 1]])
    assert model.distinct_count() == 3


def test_distinct_count_empty_script_is_zero():
    assert ScriptedModel([]).distinct_count() == 0


def test_contains_matches_a_scripted_response():
    model = ScriptedModel(["a", "b", "a"])
    assert model.contains("a")
    assert model.contains("b")
    assert not model.contains("z")


def test_contains_empty_script_is_false():
    assert not ScriptedModel([]).contains("a")


def test_contains_agrees_with_find():
    model = ScriptedModel([{"x": 1}, {"x": 2}])
    for response in ({"x": 1}, {"x": 9}):
        assert model.contains(response) == (model.find(response) is not None)


def test_tail_returns_last_responses_in_order():
    model = ScriptedModel(["a", "b", "c", "d"])
    assert model.tail(2) == ["c", "d"]
    assert model.tail(0) == []
    assert model.tail(9) == ["a", "b", "c", "d"]


def test_tail_rejects_negative():
    with pytest.raises(ValueError):
        ScriptedModel(["a"]).tail(-1)


def test_tail_and_window_agree_on_the_end():
    model = ScriptedModel(["a", "b", "c", "d"])
    assert model.tail(2) == model.window(2, 4)


def test_is_empty():
    assert ScriptedModel([]).is_empty()
    assert not ScriptedModel(["a"]).is_empty()


def test_head_returns_first_responses_in_order():
    model = ScriptedModel(["a", "b", "c"])
    assert model.head(2) == ["a", "b"]
    assert model.head(0) == []
    assert model.head(10) == ["a", "b", "c"]


def test_head_rejects_negative():
    with pytest.raises(ValueError):
        ScriptedModel(["a"]).head(-1)
