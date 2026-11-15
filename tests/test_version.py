"""Package version, project metadata and changelog agree."""
import tomllib
from pathlib import Path

import revenant

ROOT = Path(__file__).resolve().parent.parent


def test_version_matches_pyproject() -> None:
    meta = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert revenant.__version__ == meta["project"]["version"]


def test_changelog_has_current_version() -> None:
    assert f"## [{revenant.__version__}]" in (ROOT / "CHANGELOG.md").read_text()
