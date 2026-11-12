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


def test_linear_shape():
    from revenant.workloads import linear

    w = linear()
    assert w.name == "linear"
    assert len(w.steps) == 12
    assert w.tool_steps == (3, 6, 9)
    assert [w.steps[i - 1].tool for i in w.tool_steps] == [
        "send_email",
        "charge_card",
        "write_file",
    ]


def test_linear_tool_args_are_valid():
    from revenant.tools import get_tool
    from revenant.workloads import linear

    w = linear()
    for i in w.tool_steps:
        spec = w.steps[i - 1]
        get_tool(spec.tool, "/tmp/box").idempotency_key(spec.args)


def test_get_workload_registry():
    from revenant.workloads import get_workload

    assert get_workload("linear").name == "linear"
    with pytest.raises(KeyError, match="known workloads: linear"):
        get_workload("nope")
