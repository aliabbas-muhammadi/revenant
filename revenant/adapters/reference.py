"""Reference runtime: an explicit step loop, the baseline that should pass everything.

After every step the state and trace are checkpointed atomically; ``run`` resumes
from the last checkpoint in the workdir and skips completed steps.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
from pathlib import Path
from typing import Any

from revenant.adapter import Adapter
from revenant.canon import state_hash
from revenant.checkpoint import load_checkpoint, write_checkpoint
from revenant.clock import InjectedClock
from revenant.ledger import Ledger
from revenant.model import ScriptedModel
from revenant.result import RunResult
from revenant.sink import EffectSink
from revenant.tools import AttemptCounter, get_tool, invoke
from revenant.workloads import Workload, get_workload

CHECKPOINT_NAME = "checkpoint.json"
TRACE_NAME = "trace.jsonl"
KILL_ENV = "REVENANT_KILL_AT"


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
        """Run or resume. ``kill_at`` (or ``REVENANT_KILL_AT``) SIGKILLs this process
        right after the checkpoint for that step is durable."""
        if kill_at is None and os.environ.get(KILL_ENV):
            kill_at = int(os.environ[KILL_ENV])
        return self._execute(kill_at=kill_at)

    def _execute(self, stop_after: int | None = None, kill_at: int | None = None) -> RunResult:
        """Run or resume; ``stop_after`` returns early after that many total steps."""
        workload, root = self._built()
        model = ScriptedModel(workload.script)
        clock = InjectedClock(0.0)
        sink = EffectSink(root / "effects.jsonl")
        attempts = AttemptCounter()
        state: dict[str, Any] = {"step": 0, "thoughts": [], "results": {}, "clock": 0.0}
        self._trace = []
        saved = load_checkpoint(root / CHECKPOINT_NAME)
        if saved is not None:
            state = saved["state"]
            self._trace = list(saved["trace"])
            clock = InjectedClock(state["clock"])
        self._rewrite_trace_file(root)
        start = state["step"]
        with Ledger(root / "ledger.db") as ledger:
            for index in range(start, len(workload.steps)):
                if stop_after is not None and index >= stop_after:
                    return RunResult(False, len(self._trace), tuple(self._trace))
                spec = workload.steps[index]
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
                write_checkpoint(root / CHECKPOINT_NAME, {"state": state, "trace": self._trace})
                self._append_trace_line(root, index + 1, self._trace[-1])
                if kill_at is not None and index + 1 == kill_at:
                    os.kill(os.getpid(), signal.SIGKILL)
        return RunResult(True, len(self._trace), tuple(self._trace))

    def _rewrite_trace_file(self, root: Path) -> None:
        """Make the trace file match the checkpoint (a kill can leave it one line short)."""
        path = root / TRACE_NAME
        path.write_text("")
        for step, digest in enumerate(self._trace, 1):
            self._append_trace_line(root, step, digest)

    @staticmethod
    def _append_trace_line(root: Path, step: int, digest: str) -> None:
        line = json.dumps({"step": step, "hash": digest}, sort_keys=True) + "\n"
        with open(root / TRACE_NAME, "ab") as fh:
            fh.write(line.encode("utf-8"))
            fh.flush()
            os.fsync(fh.fileno())

    def state_trace(self) -> tuple[str, ...]:
        """Hashes recorded in the trace file, in step order."""
        _, root = self._built()
        path = root / TRACE_NAME
        if not path.exists():
            return ()
        rows = [json.loads(line) for line in path.read_text().splitlines() if line]
        return tuple(row["hash"] for row in rows)

    def boundaries(self) -> int:
        workload, _ = self._built()
        return len(workload.steps)


def main(argv: list[str] | None = None) -> int:
    """Child entry point: run one workload in ``--workdir``, honouring ``REVENANT_KILL_AT``."""
    parser = argparse.ArgumentParser(prog="python -m revenant.adapters.reference")
    parser.add_argument("--workload", required=True)
    parser.add_argument("--workdir", required=True)
    args = parser.parse_args(argv)
    adapter = ReferenceAdapter()
    adapter.build(get_workload(args.workload), args.workdir)
    result = adapter.run()
    print(json.dumps({"completed": result.completed, "steps_run": result.steps_run}))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
