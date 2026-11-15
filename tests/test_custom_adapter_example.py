import importlib.util
import os
import sys
from pathlib import Path

import pytest

from revenant.runner import sweep
from revenant.workloads import get_workload

pytestmark = pytest.mark.skipif(os.name != "posix", reason="needs POSIX signals")

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "custom_adapter"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"example_{name}", EXAMPLE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    sys.path.insert(0, str(EXAMPLE))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(EXAMPLE))
    return module


@pytest.mark.parametrize("mode", ["boundary", "mid"])
def test_example_passes_linear(tmp_path, mode):
    runner = _load("run_sweep")
    result = sweep(
        runner.MinimalAdapter, get_workload("linear"), tmp_path, mode=mode,
        argv_for=runner.argv_for("linear"), jobs=4,
    )  # fmt: skip
    assert result.passed, result.failing()
    assert result.duplicated == 0


def test_example_without_the_ledger_fails_mid_kills(tmp_path):
    runner = _load("run_sweep")
    naive = EXAMPLE / "adapter.py"
    source = naive.read_text().replace("sink, ledger)", "sink, ledger, naive=True)")
    assert source != naive.read_text()
    copy = tmp_path / "adapter_naive.py"
    copy.write_text(source)

    def argv_for(workdir):
        return [sys.executable, str(copy), "--workload", "linear", "--workdir", str(workdir)]

    result = sweep(
        runner.MinimalAdapter, get_workload("linear"), tmp_path / "out", mode="mid",
        boundaries=[3, 4, 6], argv_for=argv_for,
    )  # fmt: skip
    assert result.failing() == (3, 6)
