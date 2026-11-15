"""A complete minimal adapter: a step loop with an atomic checkpoint and ledgered tools."""

from __future__ import annotations

import argparse
import json
import os
import signal
from pathlib import Path

from revenant.adapter import Adapter
from revenant.canon import state_hash
from revenant.checkpoint import load_checkpoint, write_checkpoint
from revenant.ledger import Ledger
from revenant.result import RunResult
from revenant.sink import EffectSink
from revenant.tools import get_tool, invoke
from revenant.workloads import Workload, get_workload


class MinimalAdapter(Adapter):
    name = "minimal"

    def build(self, workload: Workload, workdir: str | Path) -> None:
        self.workload, self.root = workload, Path(workdir)
        self.root.mkdir(parents=True, exist_ok=True)

    def run(self, kill_at: int | None = None) -> RunResult:
        if kill_at is None and os.environ.get("REVENANT_KILL_AT"):
            kill_at = int(os.environ["REVENANT_KILL_AT"])
        mid = os.environ.get("REVENANT_KILL_MODE") == "mid"
        saved = load_checkpoint(self.root / "checkpoint.json")
        step, trace = (saved["step"], saved["trace"]) if saved else (0, [])
        sink = EffectSink(self.root / "effects.jsonl")
        with Ledger(self.root / "ledger.db") as ledger:
            for index in range(step, len(self.workload.steps)):
                spec = self.workload.steps[index]
                if spec.tool is not None:
                    tool = get_tool(spec.tool, self.root / "sandbox")
                    invoke(tool, spec.args, sink, ledger)
                if mid and kill_at == index + 1:
                    os.kill(os.getpid(), signal.SIGKILL)  # after the effect, before the checkpoint
                trace.append(state_hash({"step": index + 1, "reply": self.workload.script[index]}))
                write_checkpoint(self.root / "checkpoint.json", {"step": index + 1, "trace": trace})
                if not mid and kill_at == index + 1:
                    os.kill(os.getpid(), signal.SIGKILL)
        return RunResult(True, len(trace), tuple(trace))

    def state_trace(self) -> tuple[str, ...]:
        saved = load_checkpoint(self.root / "checkpoint.json")
        return tuple(saved["trace"]) if saved else ()

    def boundaries(self) -> int:
        return len(self.workload.steps)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workload", required=True)
    parser.add_argument("--workdir", required=True)
    args = parser.parse_args()
    adapter = MinimalAdapter()
    adapter.build(get_workload(args.workload), args.workdir)
    print(json.dumps({"completed": adapter.run().completed}))
