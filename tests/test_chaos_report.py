import json

from revenant.cli import main
from revenant.conformance import BoundaryResult, aggregate
from revenant.report import json_report, markdown_from_dict, markdown_report, summary_line
from revenant.scoring import DeterminismScore, EffectsScore, StepsScore


def _b(k, detected=None):
    return BoundaryResult(
        k, "boundary", DeterminismScore(True), EffectsScore(3, (), (), (), ()),
        StepsScore((), ()), detected,
    )  # fmt: skip


def test_plain_reports_carry_no_chaos_keys():
    r = aggregate("reference", "linear", [_b(1)])
    doc = json.loads(json_report(r, versions={}))
    assert "chaos" not in doc and "detected" not in doc["boundaries"][0]
    assert "chaos |" not in markdown_report(r)
    assert "chaos" not in summary_line(r)


def test_damage_modes_report_refusals_in_every_format():
    r = aggregate("reference", "linear", [_b(1, True), _b(2, False)], chaos="corrupt")
    line = summary_line(r)
    assert "chaos: corrupt" in line and "damage refused: 1/2" in line
    doc = json.loads(json_report(r, versions={}))
    assert doc["chaos"] == "corrupt"
    assert [b["detected"] for b in doc["boundaries"]] == [True, False]
    md = markdown_report(r)
    assert "| chaos | damage | result |" in md
    assert "refused (damage detected)" in md and "NOT detected" in md
    assert markdown_from_dict(doc) == md


def test_injection_modes_show_chaos_without_damage_counts():
    r = aggregate("reference", "linear", [_b(1)], chaos="dup")
    assert summary_line(r).endswith("chaos: dup · verdict: PASS")
    md = markdown_report(r)
    assert "| dup | - |" in md


def test_cli_writes_chaos_into_the_json_report(tmp_path):
    out = tmp_path / "r.json"
    code = main(["run", "--adapter", "reference", "--workload", "linear", "--kill-at", "4",
                 "--chaos", "corrupt", "--out", str(out)])  # fmt: skip
    assert code == 0
    doc = json.loads(out.read_text())
    assert doc["chaos"] == "corrupt" and doc["boundaries"][0]["detected"] is True
