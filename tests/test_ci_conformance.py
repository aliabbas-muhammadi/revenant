"""The CI conformance script passes on the committed adapters and covers every mutant."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MUTANTS = {"mutant_nocheckpoint", "mutant_inplace", "mutant_volatile",
           "mutant_checkpoint_first", "mutant_noledger"}


def test_script_names_every_mutant() -> None:
    text = (ROOT / "scripts" / "ci_conformance.sh").read_text()
    for m in MUTANTS:
        assert m in text


def test_script_runs_green(tmp_path: Path) -> None:
    proc = subprocess.run(["bash", str(ROOT / "scripts" / "ci_conformance.sh"), str(tmp_path)],
                          capture_output=True, text=True, cwd=ROOT)
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "reference-linear.json").exists()
    for m in MUTANTS:
        assert json.loads((tmp_path / f"{m}-linear.json").read_text())


def test_ci_workflow_runs_conformance() -> None:
    assert "make ci-conformance" in (ROOT / ".github" / "workflows" / "ci.yml").read_text()


def test_langgraph_target_and_job() -> None:
    assert "ci-langgraph:" in (ROOT / "Makefile").read_text()
    assert "make ci-langgraph" in (ROOT / ".github" / "workflows" / "ci.yml").read_text()


def test_langgraph_target_runs(tmp_path: Path) -> None:
    proc = subprocess.run(["make", "ci-langgraph"], capture_output=True, text=True, cwd=ROOT)
    assert proc.returncode == 0, proc.stderr
    assert "PASS" in proc.stdout
