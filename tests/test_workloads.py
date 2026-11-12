import pytest

from revenant.workloads import StepSpec, Workload


def test_construction_and_tool_steps():
    w = Workload(
        "w",
        (StepSpec("a"), StepSpec("b", "send_email", {"to": "x"}), StepSpec("c")),
        ("r1", "r2", "r3"),
        volatile_fields=("meta.ts",),
    )
    assert w.tool_steps == (2,)
    assert w.volatile_fields == ("meta.ts",)


def test_empty_steps_rejected():
    with pytest.raises(ValueError, match="no steps"):
        Workload("w", (), ())


def test_script_length_must_match():
    with pytest.raises(ValueError, match="script has 1"):
        Workload("w", (StepSpec("a"), StepSpec("b")), ("r",))


def test_name_required():
    with pytest.raises(ValueError, match="name"):
        Workload("", (StepSpec("a"),), ("r",))
