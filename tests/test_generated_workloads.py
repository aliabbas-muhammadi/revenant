"""Seeded random workloads: determinism, validity and a reference sweep."""

import os
import sys

import pytest

from revenant.adapters.reference import ReferenceAdapter
from revenant.runner import sweep
from revenant.workloads import generate, get_workload

SEEDS = (1, 2, 3)


def test_same_seed_same_workload():
    assert generate(7) == generate(7)


def test_seeds_differ():
    assert len({repr(generate(s).steps) for s in range(10)}) > 1


def test_name_round_trips_through_get_workload():
    assert get_workload("gen-5") == generate(5)


@pytest.mark.parametrize("name", ["gen-", "gen-x"])
def test_bad_generated_name(name):
    with pytest.raises(KeyError, match="gen-<integer seed>"):
        get_workload(name)


@pytest.mark.parametrize("seed", range(30))
def test_layout_is_valid(seed):
    wl = generate(seed)
    assert 4 <= len(wl.steps) <= 14
    assert len(wl.script) == len(wl.steps)
    paths = [s.args["relpath"] for s in wl.steps if s.tool == "write_file"]
    assert len(paths) == len(set(paths))


@pytest.mark.skipif(os.name != "posix", reason="needs POSIX signals")
@pytest.mark.parametrize("seed", SEEDS)
def test_reference_passes_generated_workload(tmp_path, seed):
    name = f"gen-{seed}"

    def argv_for(workdir):
        return [sys.executable, "-m", "revenant.adapters.reference",
                "--workload", name, "--workdir", str(workdir)]  # fmt: skip

    res = sweep(ReferenceAdapter, get_workload(name), tmp_path, argv_for=argv_for, jobs=4)
    assert res.passed, res.failing()
    assert res.unconfirmed == 0
