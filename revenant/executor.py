"""In-process executor: runs a workload with no runtime and returns its trace.

This is the plain reference semantics used by tests. There is no checkpointing
and no resume, so it only answers "what does a clean run look like".
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from revenant.canon import state_hash
from revenant.clock import InjectedClock
from revenant.ledger import Ledger
from revenant.model import ScriptedModel
from revenant.sink import EffectSink
from revenant.tools import AttemptCounter, get_tool, invoke
from revenant.workloads import Workload


@dataclass(frozen=True)
class ExecutionResult:
    """Per-step state hashes plus the final state."""

    trace: tuple[str, ...]
    state: dict[str, Any]
    attempts: dict[str, int]


def execute(workload: Workload, workdir: str | Path, naive: bool = False) -> ExecutionResult:
    """Run every step in order and hash the state after each one."""
    root = Path(workdir)
    root.mkdir(parents=True, exist_ok=True)
    model = ScriptedModel(workload.script)
    clock = InjectedClock(0.0)
    sink = EffectSink(root / "effects.jsonl")
    attempts = AttemptCounter()
    state: dict[str, Any] = {"step": 0, "thoughts": [], "results": {}, "clock": 0.0}
    trace: list[str] = []
    with Ledger(root / "ledger.db") as ledger:
        for index, spec in enumerate(workload.steps):
            response = model.respond(index)
            clock.tick()
            if spec.tool is not None:
                tool = get_tool(spec.tool, root / "sandbox")
                outcome = invoke(tool, spec.args, sink, ledger, attempts, naive=naive)
                state["results"][spec.name] = outcome.key
            state["step"] = index + 1
            state["thoughts"].append(response)
            state["clock"] = clock.now()
            trace.append(state_hash(state, workload.volatile_fields))
    return ExecutionResult(tuple(trace), state, attempts.by_tool())
