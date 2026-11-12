"""Reference runtime: an explicit step loop, the baseline that should pass everything.

This first version runs a workload in-process with no checkpointing. Durability
is layered on in the following changes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from revenant.adapter import Adapter
from revenant.canon import state_hash
from revenant.clock import InjectedClock
from revenant.ledger import Ledger
from revenant.model import ScriptedModel
from revenant.result import RunResult
from revenant.sink import EffectSink
from revenant.tools import AttemptCounter, get_tool, invoke
from revenant.workloads import Workload


class ReferenceAdapter(Adapter):
    """Step loop over a workload: model response, tool call, state hash."""

    name = "reference"

    def __init__(self) -> None:
        self._workload: Workload | None = None
        self._workdir: Path | None = None
        self._trace: list[str] = []

    def build(self, workload: Workload, workdir: str | Path) -> None:
        self._workload = workload
        self._workdir = Path(workdir)
        self._workdir.mkdir(parents=True, exist_ok=True)
        self._trace = []

    def _built(self) -> tuple[Workload, Path]:
        if self._workload is None or self._workdir is None:
            raise RuntimeError("call build() before run()")
        return self._workload, self._workdir

    def run(self, kill_at: int | None = None) -> RunResult:
        workload, root = self._built()
        model = ScriptedModel(workload.script)
        clock = InjectedClock(0.0)
        sink = EffectSink(root / "effects.jsonl")
        attempts = AttemptCounter()
        state: dict[str, Any] = {"step": 0, "thoughts": [], "results": {}, "clock": 0.0}
        self._trace = []
        with Ledger(root / "ledger.db") as ledger:
            for index, spec in enumerate(workload.steps):
                response = model.respond(index)
                clock.tick()
                if spec.tool is not None:
                    tool = get_tool(spec.tool, root / "sandbox")
                    outcome = invoke(tool, spec.args, sink, ledger, attempts)
                    state["results"][spec.name] = outcome.key
                state["step"] = index + 1
                state["thoughts"].append(response)
                state["clock"] = clock.now()
                self._trace.append(state_hash(state, workload.volatile_fields))
        return RunResult(True, len(self._trace), tuple(self._trace))

    def state_trace(self) -> tuple[str, ...]:
        return tuple(self._trace)

    def boundaries(self) -> int:
        workload, _ = self._built()
        return len(workload.steps)
