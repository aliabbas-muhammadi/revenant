import json

import pytest

from revenant.adapters.reference import ReferenceAdapter
from revenant.report import json_report
from revenant.runner import sweep
from revenant.workloads import get_workload

#: Fields allowed to differ between runs (timings); removed before comparing.
VOLATILE_KEYS = {"wall_seconds"}


def strip_volatile(node):
    """Return ``node`` with every volatile timing field removed, recursively."""
    if isinstance(node, dict):
        return {k: strip_volatile(v) for k, v in node.items() if k not in VOLATILE_KEYS}
    if isinstance(node, list):
        return [strip_volatile(v) for v in node]
    return node


def _report(root):
    result = sweep(ReferenceAdapter, get_workload("linear"), root, jobs=2)
    return strip_volatile(json.loads(json_report(result)))


def test_strip_volatile_removes_nested_fields():
    doc = {"a": 1, "wall_seconds": 3, "b": [{"wall_seconds": 1, "c": 2}]}
    assert strip_volatile(doc) == {"a": 1, "b": [{"c": 2}]}


@pytest.mark.parametrize("workload", ["linear"])
def test_two_full_sweeps_are_byte_identical(tmp_path, workload):
    first = _report(tmp_path / "a")
    second = _report(tmp_path / "b")
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["verdict"] == "PASS"


def test_sweep_records_wall_time_per_boundary():
    import tempfile

    with tempfile.TemporaryDirectory() as root:
        result = sweep(ReferenceAdapter, get_workload("linear"), root, boundaries=[2, 3])
    assert all(b.wall_seconds is not None and b.wall_seconds >= 0 for b in result.boundaries)
    raw = json.loads(json_report(result))
    assert all("wall_seconds" in b for b in raw["boundaries"])
    assert all("wall_seconds" not in b for b in strip_volatile(raw)["boundaries"])
