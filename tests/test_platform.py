import signal

import pytest

from revenant.adapters.reference import ReferenceAdapter
from revenant.cli import main
from revenant.runner import UnsupportedPlatform, require_sigkill, sweep
from revenant.workloads import get_workload


def test_sigkill_present_is_accepted():
    if hasattr(signal, "SIGKILL"):
        require_sigkill()


def test_missing_sigkill_raises_clear_error(monkeypatch, tmp_path):
    monkeypatch.delattr(signal, "SIGKILL", raising=False)
    with pytest.raises(UnsupportedPlatform, match="SIGKILL"):
        require_sigkill()
    with pytest.raises(UnsupportedPlatform):
        sweep(ReferenceAdapter, get_workload("linear"), tmp_path)


def test_cli_reports_usage_error(monkeypatch, capsys):
    monkeypatch.delattr(signal, "SIGKILL", raising=False)
    with pytest.raises(SystemExit) as exc:
        main(["run", "--adapter", "reference", "--workload", "linear"])
    assert exc.value.code == 2
    assert "SIGKILL" in capsys.readouterr().err
