import os
import sys

import pytest

from revenant.adapters.mutant_volatile import FIELD, VolatileMutant
from revenant.runner import sweep
from revenant.workloads import get_workload

posix = pytest.mark.skipif(os.name != "posix", reason="needs POSIX signals")


def _argv(workdir):
    return [sys.executable, "-m", "revenant.adapters.mutant_volatile",
            "--workload", "linear", "--workdir", str(workdir)]  # fmt: skip


@posix
def test_undeclared_timestamp_breaks_determinism_only(tmp_path):
    res = sweep(
        VolatileMutant, get_workload("linear"), tmp_path,
        boundaries=[3, 6], argv_for=_argv,
    )  # fmt: skip
    assert not res.passed
    assert res.failing() == (3, 6)
    for b in res.boundaries:
        assert not b.determinism.passed
        assert b.determinism.first_divergent_step == b.boundary + 1
        assert b.effects.passed and b.steps.passed


def test_declaring_the_field_volatile_restores_determinism(tmp_path):
    from dataclasses import replace

    wl = get_workload("linear")
    declared = replace(wl, volatile_fields=(*wl.volatile_fields, FIELD))
    a, b = VolatileMutant(), VolatileMutant()
    a.build(declared, tmp_path / "a")
    b.build(declared, tmp_path / "b")
    assert a.run().trace == b.run().trace
