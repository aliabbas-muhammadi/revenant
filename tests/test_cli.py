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


def _saved_report(tmp_path):
    from test_conformance import _b

    from revenant.conformance import aggregate
    from revenant.report import json_report

    path = tmp_path / "r.json"
    path.write_text(json_report(aggregate("a", "w", [_b(1), _b(2)]), versions={"python": "x"}))
    return path


def test_report_formats(tmp_path, capsys):
    path = _saved_report(tmp_path)
    assert main(["report", str(path)]) == 0
    assert capsys.readouterr().out.startswith("killed at 2/2 boundaries")
    assert main(["report", str(path), "--format", "md"]) == 0
    assert capsys.readouterr().out.startswith("# a · w")
    assert main(["report", str(path), "--format", "json"]) == 0
    assert capsys.readouterr().out == path.read_text()


def test_report_rejects_bad_input(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{}")
    for target in (bad, tmp_path / "missing.json"):
        with pytest.raises(SystemExit) as exc:
            main(["report", str(target)])
        assert exc.value.code == 2


def test_list_shows_adapters_and_workloads(capsys):
    assert main(["list"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out == [
        "adapters:  reference",
        "workloads: linear, branching, fanout",
    ]


def test_exit_code_one_for_a_failing_report(tmp_path, capsys):
    from test_conformance import _b

    from revenant.conformance import aggregate
    from revenant.report import json_report

    path = tmp_path / "fail.json"
    path.write_text(json_report(aggregate("a", "w", [_b(1, ok=False)]), versions={}))
    assert main(["report", str(path)]) == 1
    assert capsys.readouterr().out.endswith("verdict: FAIL\n")


def test_exit_code_zero_for_pass_with_unconfirmed(tmp_path):
    from test_conformance import _b

    from revenant.conformance import aggregate
    from revenant.report import json_report

    path = tmp_path / "u.json"
    path.write_text(json_report(aggregate("a", "w", [_b(1, unconf=["k"])]), versions={}))
    assert main(["report", str(path)]) == 0


@pytest.mark.parametrize(
    "argv",
    [
        ["run"],
        ["run", "--adapter", "reference"],
        ["run", "--adapter", "reference", "--workload", "linear", "--jobs", "0"],
        ["run", "--adapter", "reference", "--workload", "linear", "--mode", "bogus"],
        ["report"],
        ["frobnicate"],
    ],
)
def test_usage_errors_exit_two(argv):
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == 2
