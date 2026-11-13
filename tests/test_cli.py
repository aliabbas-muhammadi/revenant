import pytest

from revenant import __version__
from revenant.cli import main


def test_main_without_args_prints_help(capsys):
    assert main([]) == 0
    assert "usage: revenant" in capsys.readouterr().out


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_run_reports_a_passing_sweep(capsys):
    assert main(["run", "--adapter", "reference", "--workload", "linear", "--jobs", "4"]) == 0
    out = capsys.readouterr().out.strip()
    assert out == (
        "killed at 12/12 boundaries · resumes: 12/12 identical · effects: 3 once each"
        " · unconfirmed: 0 · verdict: PASS"
    )


def test_run_single_boundary_in_mid_mode(capsys):
    argv = ["run", "--adapter", "reference", "--workload", "linear",
            "--kill-at", "5", "--mode", "mid"]  # fmt: skip
    assert main(argv) == 0
    assert capsys.readouterr().out.startswith("killed at 1/1 boundaries")


def test_run_rejects_unknown_adapter_and_workload(capsys):
    for argv in (["run", "--adapter", "nope", "--workload", "linear"],
                 ["run", "--adapter", "reference", "--workload", "nope"]):  # fmt: skip
        with pytest.raises(SystemExit) as exc:
            main(argv)
        assert exc.value.code == 2
    assert "known" in capsys.readouterr().err
