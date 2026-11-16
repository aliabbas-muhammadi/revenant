"""Each mutant must be caught on generated workloads too, not only on `linear`."""

import importlib
import os
import sys

import pytest

from revenant.runner import sweep
from revenant.workloads import get_workload

pytestmark = pytest.mark.skipif(os.name != "posix", reason="needs POSIX signals")

SEEDS = (1, 2, 3)
MUTANTS = [
    ("mutant_nocheckpoint", "NoCheckpointMutant", "boundary"),
    ("mutant_inplace", "InPlaceMutant", "boundary"),
    ("mutant_checkpoint_first", "CheckpointFirstMutant", "mid"),
    ("mutant_noledger", "NoLedgerMutant", "mid"),
    ("mutant_volatile", "VolatileMutant", "boundary"),
]


@pytest.mark.parametrize(("module", "cls", "mode"), MUTANTS, ids=[m[0] for m in MUTANTS])
def test_mutant_fails_on_some_generated_workload(tmp_path, module, cls, mode):
    factory = getattr(importlib.import_module(f"revenant.adapters.{module}"), cls)
    caught = []
    for seed in SEEDS:
        name = f"gen-{seed}"

        def argv_for(workdir, name=name):
            return [sys.executable, "-m", f"revenant.adapters.{module}",
                    "--workload", name, "--workdir", str(workdir)]  # fmt: skip

        res = sweep(
            factory, get_workload(name), tmp_path / name,
            mode=mode, argv_for=argv_for, jobs=4,
        )  # fmt: skip
        if not res.passed:
            caught.append(name)
    assert caught, f"{module} passed every generated workload"
