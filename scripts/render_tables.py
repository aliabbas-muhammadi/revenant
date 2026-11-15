"""Render the README headline table from the committed reports in ``results/``.

``python scripts/render_tables.py`` rewrites the block between the table markers in
README.md; ``--check`` exits 1 if the README is out of date instead of writing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
START = "<!-- results-table:start -->"
END = "<!-- results-table:end -->"
HEADER = (
    "| result | adapter | workload | kill mode | chaos | boundaries passed | "
    "duplicated | unconfirmed | verdict |\n"
    "|---|---|---|---|---|---:|---:|---:|---|"
)


def _row(results: Path, path: Path) -> str:
    data = json.loads(path.read_text())
    bounds = data["boundaries"]
    modes = "+".join(sorted({b["mode"] for b in bounds}))
    passed = sum(1 for b in bounds if b["passed"])
    dup = sum(len(b["effects"]["duplicated"]) for b in bounds)
    unconfirmed = sum(len(b["effects"]["unconfirmed"]) for b in bounds)
    label = path.relative_to(results).with_suffix("").as_posix()
    link = f"[{label}](results/{path.relative_to(results).as_posix()})"
    chaos = data.get("chaos", "none")
    return (
        f"| {link} | {data['adapter']} | {data['workload']} | {modes} | {chaos} | "
        f"{passed}/{len(bounds)} | {dup} | {unconfirmed} | {data['verdict']} |"
    )


def render(results: Path = ROOT / "results") -> str:
    """The table for every ``*.json`` report under ``results``, in path order."""
    paths = sorted(results.rglob("*.json"), key=lambda p: p.relative_to(results).as_posix())
    return "\n".join([HEADER, *(_row(results, p) for p in paths)])


def update(readme: str, table: str) -> str:
    """Return ``readme`` with the marked block replaced by ``table``."""
    head, sep, rest = readme.partition(START)
    if not sep or END not in rest:
        raise ValueError(f"README needs the {START} and {END} markers")
    _, _, tail = rest.partition(END)
    return f"{head}{START}\n{table}\n{END}{tail}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if README is stale")
    args = parser.parse_args(argv)
    readme_path = ROOT / "README.md"
    current = readme_path.read_text()
    fresh = update(current, render())
    if args.check:
        if fresh != current:
            print("README results table is stale; run scripts/render_tables.py", file=sys.stderr)
            return 1
        return 0
    readme_path.write_text(fresh)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
