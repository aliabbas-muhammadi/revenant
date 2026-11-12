import pytest

from revenant.adapter import Adapter, RunResult


def test_adapter_cannot_be_instantiated():
    with pytest.raises(TypeError):
        Adapter()  # type: ignore[abstract]


def test_partial_adapter_cannot_be_instantiated():
    class Partial(Adapter):
        def build(self, workload, workdir):
            pass

    with pytest.raises(TypeError):
        Partial()  # type: ignore[abstract]


def test_complete_adapter_instantiates():
    class Full(Adapter):
        name = "full"

        def build(self, workload, workdir):
            pass

        def run(self, kill_at=None):
            return RunResult(True, 0, ())

        def state_trace(self):
            return ()

        def boundaries(self):
            return 0

    assert Full().run().completed
