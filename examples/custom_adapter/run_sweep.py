"""Sweep the example adapter: ``python examples/custom_adapter/run_sweep.py [workload]``."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from revenant.runner import sweep
from revenant.workloads import get_workload

sys.path.insert(0, str(Path(__file__).resolve().parent))
from adapter import MinimalAdapter  # noqa: E402

ADAPTER_FILE = Path(__file__).resolve().parent / "adapter.py"


def argv_for(workload: str):
    def build(workdir: Path) -> list[str]:
        return [sys.executable, str(ADAPTER_FILE),
                "--workload", workload, "--workdir", str(workdir)]  # fmt: skip

    return build


def main(workload: str = "linear") -> int:
    status = 0
    with tempfile.TemporaryDirectory() as tmp:
        for mode in ("boundary", "mid"):
            result = sweep(MinimalAdapter, get_workload(workload), Path(tmp) / mode,
                           mode=mode, argv_for=argv_for(workload), jobs=4)  # fmt: skip
            print(f"{mode}: {'PASS' if result.passed else 'FAIL'} {result.failing()}")
            status |= 0 if result.passed else 1
    return status


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:2]))
