import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "render_tables.py"
spec = importlib.util.spec_from_file_location("render_tables", SCRIPT)
render_tables = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render_tables)


def _report(**over):
    base = {
        "adapter": "a", "workload": "w", "verdict": "PASS",
        "boundaries": [
            {"mode": "mid", "passed": True,
             "effects": {"duplicated": [], "unconfirmed": []}},
            {"mode": "mid", "passed": False,
             "effects": {"duplicated": ["k"], "unconfirmed": ["u", "v"]}},
        ],
    }  # fmt: skip
    return {**base, **over}


def test_readme_matches_rendered_results():
    readme = (ROOT / "README.md").read_text()
    assert render_tables.update(readme, render_tables.render()) == readme


def test_row_counts_boundaries_duplicates_and_unconfirmed(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "x.json").write_text(json.dumps(_report(chaos="dup")))
    table = render_tables.render(tmp_path).splitlines()
    assert table[-1] == (
        "| [sub/x](results/sub/x.json) | a | w | mid | dup | 1/2 | 1 | 2 | PASS |"
    )


def test_update_requires_markers():
    with pytest.raises(ValueError):
        render_tables.update("no markers", "t")


def test_update_is_idempotent():
    text = f"a\n{render_tables.START}\nold\n{render_tables.END}\nb\n"
    once = render_tables.update(text, "T")
    assert once == f"a\n{render_tables.START}\nT\n{render_tables.END}\nb\n"
    assert render_tables.update(once, "T") == once
