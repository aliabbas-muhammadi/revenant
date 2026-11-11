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
