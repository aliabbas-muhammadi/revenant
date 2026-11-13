"""Every mutant must fail exactly the properties its bug violates, and no others."""

import importlib
import os
import sys

import pytest

from revenant.runner import sweep
from revenant.workloads import get_workload

posix = pytest.mark.skipif(os.name != "posix", reason="needs POSIX signals")

DET, EFF, STEPS = "determinism", "effects", "steps"

# module, class, kill mode, properties that must fail
MATRIX = [
    ("mutant_nocheckpoint", "NoCheckpointMutant", "boundary", {EFF}),
    ("mutant_inplace", "InPlaceMutant", "boundary", {DET, EFF, STEPS}),
    ("mutant_checkpoint_first", "CheckpointFirstMutant", "mid", {EFF}),
    ("mutant_noledger", "NoLedgerMutant", "mid", {EFF}),
    ("mutant_volatile", "VolatileMutant", "boundary", {DET}),
]


@posix
@pytest.mark.parametrize(("module", "cls", "mode", "expected"), MATRIX, ids=[m[0] for m in MATRIX])
def test_mutant_fails_its_expected_properties_only(tmp_path, module, cls, mode, expected):
    factory = getattr(importlib.import_module(f"revenant.adapters.{module}"), cls)

    def argv_for(workdir):
        return [sys.executable, "-m", f"revenant.adapters.{module}",
                "--workload", "linear", "--workdir", str(workdir)]  # fmt: skip

    res = sweep(
        factory, get_workload("linear"), tmp_path,
        mode=mode, boundaries=[3, 6], argv_for=argv_for,
    )  # fmt: skip
    assert not res.passed
    for b in res.boundaries:
        failed = {
            name
            for name, score in ((DET, b.determinism), (EFF, b.effects), (STEPS, b.steps))
            if not score.passed
        }
        assert failed == expected, f"{module} at {b.boundary}: failed {sorted(failed)}"
