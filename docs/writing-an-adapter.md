# Writing an adapter

An adapter wraps one runtime behind four operations (`revenant.adapter.Adapter`):

| method | contract |
|---|---|
| `build(workload, workdir)` | Prepare the runtime. All durable state, including checkpoints, the ledger and the effect sink, lives under `workdir`. |
| `run(kill_at=None)` | Run or resume to completion. When `kill_at` is `k` (or `REVENANT_KILL_AT=k` is set in the child), the process `SIGKILL`s itself at boundary `k`. |
| `state_trace()` | The per-step state hashes recorded so far, read from disk, in step order. |
| `boundaries()` | How many kill boundaries the built workload exposes. |

## How the harness drives it

For each boundary the runner starts your adapter as a **child process** with
`REVENANT_KILL_AT=k`, waits for it to die, reads `state_trace()` from the workdir, starts a
second child without the kill variable to resume, and reads the trace again. So an adapter
needs a command line: a small `main` taking `--workload` and `--workdir` and calling
`build` then `run`. Pass that command to `sweep(..., argv_for=...)`.

Your runtime must satisfy a few rules, or the sweep reports failures that are really bugs
in the adapter:

1. **Die with `SIGKILL`, not by raising.** `os.kill(os.getpid(), signal.SIGKILL)` skips
   every cleanup handler, which is the point.
2. **Kill on the step counter.** Never use timers.
3. **Two kill modes.** The default (`boundary`) kills right after step `k`'s checkpoint is
   durable. With `REVENANT_KILL_MODE=mid` the child dies after step `k`'s tool call but
   before its checkpoint: this is the window where duplicate effects appear.
4. **Resume from disk only.** The resumed child shares nothing with the killed one except
   the workdir.
5. **Hash deterministic state.** Use `revenant.canon.state_hash`; pass a workload's
   `volatile_fields` if your state carries timestamps or durations, or every resume will
   look like a divergence.
6. **Route tool calls through the ledger.** `revenant.tools.invoke` records intent, performs
   the effect in the sink, and commits, suppressing a repeat of a committed key.
7. **Make checkpoints atomic.** `revenant.checkpoint.write_checkpoint` writes a temp file,
   fsyncs it, renames it over the target and fsyncs the directory.

## A complete minimal adapter

This adapter is a 12-step loop with an atomic checkpoint and ledgered tools. It passes
`linear` at every boundary in both kill modes. It also lives in
[examples/custom_adapter/](../examples/custom_adapter/), where `tests/test_custom_adapter_example.py`
keeps it passing.

```python
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
```

## Running it

```python
import sys
from pathlib import Path
from revenant.runner import sweep
from revenant.workloads import get_workload

def argv_for(workdir):
    return [sys.executable, "minimal.py", "--workload", "linear", "--workdir", str(workdir)]

for mode in ("boundary", "mid"):
    result = sweep(MinimalAdapter, get_workload("linear"), Path("out") / mode,
                   mode=mode, argv_for=argv_for)
    print(mode, result.passed, result.failing())
```

Both modes pass. To see the harness catch a bug, pass `naive=True` to `invoke`, which
bypasses the ledger: boundary kills still pass, but `mid` kills at 3, 6 and 9 fail with a
duplicated effect, because the resume repeats a step whose effect already happened.

## Registering with the CLI

The CLI looks adapters up in `revenant.cli.ADAPTERS` and runs each one as
`python -m revenant.adapters.<name>`. An adapter that lives outside the package is driven
through `sweep` as above.
