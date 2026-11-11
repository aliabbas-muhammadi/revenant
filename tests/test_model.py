import pytest

from revenant.model import ScriptedModel, ScriptExhausted


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
