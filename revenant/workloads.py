"""Workloads: deterministic step layouts, model scripts and volatile fields."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StepSpec:
    """One step: an optional tool call with fixed arguments."""

    name: str
    tool: str | None = None
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Workload:
    """An ordered list of steps plus the scripted model that drives them.

    ``script`` holds one model response per step. ``volatile_fields`` are the
    state paths excluded from hashing (see :func:`revenant.canon.state_hash`).
    """

    name: str
    steps: tuple[StepSpec, ...]
    script: tuple[Any, ...]
    volatile_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("workload needs a name")
        if not self.steps:
            raise ValueError(f"workload {self.name!r} has no steps")
        if len(self.script) != len(self.steps):
            raise ValueError(
                f"workload {self.name!r}: script has {len(self.script)} responses "
                f"for {len(self.steps)} steps"
            )

    @property
    def tool_steps(self) -> tuple[int, ...]:
        """1-based positions of the steps that call a tool."""
        return tuple(i for i, s in enumerate(self.steps, 1) if s.tool is not None)


def linear() -> Workload:
    """12 steps; steps 3, 6 and 9 each call one tool."""
    tools: dict[int, StepSpec] = {
        3: StepSpec(
            "email",
            "send_email",
            {"to": "ops@example.com", "subject": "report", "body": "step 3 done"},
        ),
        6: StepSpec("charge", "charge_card", {"customer": "cus_1", "amount_cents": 1999}),
        9: StepSpec(
            "write",
            "write_file",
            {"relpath": "out/summary.txt", "content": "summary at step 9"},
        ),
    }
    steps = tuple(tools.get(i, StepSpec(f"step{i}")) for i in range(1, 13))
    script = tuple({"thought": f"thought {i}"} for i in range(1, 13))
    return Workload("linear", steps, script)


_FACTORIES = {"linear": linear}
WORKLOAD_NAMES = tuple(_FACTORIES)


def get_workload(name: str) -> Workload:
    """Build a workload by name; unknown names list the known ones."""
    try:
        return _FACTORIES[name]()
    except KeyError:
        raise KeyError(
            f"unknown workload {name!r}; known workloads: {', '.join(WORKLOAD_NAMES)}"
        ) from None
