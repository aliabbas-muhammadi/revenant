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
