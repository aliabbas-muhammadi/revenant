"""Workloads: deterministic step layouts, model scripts and volatile fields."""

from __future__ import annotations

import random
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


def branching() -> Workload:
    """A tool loop: the scripted model keeps calling tools, then says stop.

    Nine tool-call steps (a mix of the three tools) followed by a stop step,
    10 steps in all. Each step's script entry is ``{"action": "call", ...}``
    or ``{"action": "stop"}``; the executor stops once it sees the latter.
    """
    calls: list[StepSpec] = []
    for n in range(1, 10):
        if n % 3 == 1:
            spec = StepSpec(
                f"email{n}",
                "send_email",
                {"to": f"user{n}@example.com", "subject": f"update {n}", "body": f"body {n}"},
            )
        elif n % 3 == 2:
            spec = StepSpec(
                f"charge{n}", "charge_card", {"customer": f"cus_{n}", "amount_cents": 100 * n}
            )
        else:
            spec = StepSpec(
                f"write{n}",
                "write_file",
                {"relpath": f"out/note{n}.txt", "content": f"note {n}"},
            )
        calls.append(spec)
    steps = (*calls, StepSpec("stop"))
    script = (
        *({"action": "call", "tool": c.tool, "args": c.args} for c in calls),
        {"action": "stop"},
    )
    return Workload("branching", steps, script)


def fanout() -> Workload:
    """Three branches with one tool call each, merged in a final step.

    Serialised order (the total order every boundary is counted in): step 1
    ``split``, steps 2-4 the branches ``a``, ``b``, ``c`` in that order, step 5
    ``merge``. Adapters that run branches in parallel (for example LangGraph
    supersteps) define their own boundaries and say so in the report.
    """
    branches = (
        StepSpec(
            "branch_a",
            "send_email",
            {"to": "a@example.com", "subject": "branch a", "body": "from a"},
        ),
        StepSpec("branch_b", "charge_card", {"customer": "cus_b", "amount_cents": 500}),
        StepSpec(
            "branch_c", "write_file", {"relpath": "out/c.txt", "content": "from c"}
        ),
    )
    steps = (StepSpec("split"), *branches, StepSpec("merge"))
    script = (
        {"action": "split", "branches": ["a", "b", "c"]},
        *({"action": "branch", "branch": b, "tool": s.tool, "args": s.args}
          for b, s in zip("abc", branches, strict=True)),
        {"action": "merge", "branches": ["a", "b", "c"]},
    )
    return Workload("fanout", steps, script)


GENERATED_PREFIX = "gen-"
LOOP_PREFIX = "genloop-"


def generate(seed: int) -> Workload:
    """A linear-style workload whose layout is drawn from ``seed``.

    Between 4 and 14 steps; each step calls a tool with probability 1/3, the
    tool chosen at random. Arguments are derived from the step number so file
    paths never collide. The same seed always yields the same workload, and it
    is named ``gen-<seed>`` so a child process can rebuild it from the name.
    """
    rng = random.Random(seed)
    count = rng.randint(4, 14)
    steps: list[StepSpec] = []
    for n in range(1, count + 1):
        if rng.random() >= 1 / 3:
            steps.append(StepSpec(f"step{n}"))
            continue
        steps.append(_tool_spec(rng, n))
    script = tuple({"thought": f"thought {i}"} for i in range(1, count + 1))
    return Workload(f"{GENERATED_PREFIX}{seed}", tuple(steps), script)


def _tool_spec(rng: random.Random, n: int) -> StepSpec:
    tool = rng.choice(("send_email", "charge_card", "write_file"))
    if tool == "send_email":
        args: dict[str, Any] = {
            "to": f"user{n}@example.com",
            "subject": f"update {n}",
            "body": f"body {n}",
        }
    elif tool == "charge_card":
        args = {"customer": f"cus_{n}", "amount_cents": 100 * n + rng.randint(0, 99)}
    else:
        args = {"relpath": f"out/gen{n}.txt", "content": f"content {n}"}
    return StepSpec(f"{tool}{n}", tool, args)


def generate_loop(seed: int) -> Workload:
    """A branching-style tool loop whose stop point is drawn from ``seed``.

    Between 2 and 10 tool calls, then a stop step. Named ``genloop-<seed>``.
    """
    rng = random.Random(seed)
    calls = [_tool_spec(rng, n) for n in range(1, rng.randint(2, 10) + 1)]
    steps = (*calls, StepSpec("stop"))
    script = (
        *({"action": "call", "tool": c.tool, "args": c.args} for c in calls),
        {"action": "stop"},
    )
    return Workload(f"{LOOP_PREFIX}{seed}", steps, script)


_FACTORIES = {"linear": linear, "branching": branching, "fanout": fanout}
WORKLOAD_NAMES = tuple(_FACTORIES)


def get_workload(name: str) -> Workload:
    """Build a workload by name; unknown names list the known ones."""
    for prefix, build in ((GENERATED_PREFIX, generate), (LOOP_PREFIX, generate_loop)):
        if name.startswith(prefix):
            try:
                return build(int(name[len(prefix) :]))
            except ValueError:
                raise KeyError(
                    f"bad generated workload {name!r}; use {prefix}<integer seed>"
                ) from None
    try:
        return _FACTORIES[name]()
    except KeyError:
        raise KeyError(
            f"unknown workload {name!r}; known workloads: {', '.join(WORKLOAD_NAMES)}"
        ) from None
