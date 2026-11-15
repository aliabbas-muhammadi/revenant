import copy
import json
from pathlib import Path

from revenant.cli import main
from revenant.diff import diff_reports

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "results" / "reference-linear.json"
MUT = ROOT / "results" / "mutants" / "mutant_inplace-linear.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def test_identical_reports_have_no_diff() -> None:
    data = _load(REF)
    assert diff_reports(data, copy.deepcopy(data)) == []


def test_volatile_fields_are_ignored() -> None:
    a = _load(REF)
    b = copy.deepcopy(a)
    for entry in b["boundaries"]:
        entry["wall_seconds"] = 99.0
    assert diff_reports(a, b) == []


def test_field_change_is_located() -> None:
    a = _load(REF)
    b = copy.deepcopy(a)
    b["boundaries"][2]["effects"]["once"] = 1
    lines = diff_reports(a, b)
    assert lines == [f"boundary {a['boundaries'][2]['boundary']}: effects.once: 3 -> 1"]


def test_missing_boundary_reported() -> None:
    a = _load(REF)
    b = copy.deepcopy(a)
    dropped = b["boundaries"].pop()["boundary"]
    assert f"boundary {dropped}: only in A" in diff_reports(a, b)


def test_cli_exit_codes(capsys) -> None:
    assert main(["diff", str(REF), str(REF)]) == 0
    assert "equivalent" in capsys.readouterr().out
    assert main(["diff", str(REF), str(MUT)]) == 1
    assert "verdict: 'PASS' -> 'FAIL'" in capsys.readouterr().out
