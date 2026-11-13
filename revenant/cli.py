"""Command-line entry point."""

from __future__ import annotations

import argparse
import tempfile

from revenant import __version__
from revenant.adapters.reference import ReferenceAdapter
from revenant.report import summary_line
from revenant.runner import AdapterFactory, sweep
from revenant.workloads import get_workload

ADAPTERS: dict[str, AdapterFactory] = {"reference": ReferenceAdapter}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="revenant", description=__doc__)
    parser.add_argument("--version", action="version", version=f"revenant {__version__}")
    sub = parser.add_subparsers(dest="command")
    run = sub.add_parser("run", help="kill and resume a workload, then score it")
    run.add_argument("--adapter", required=True)
    run.add_argument("--workload", required=True)
    run.add_argument("--kill-at", type=int, default=None, help="one boundary instead of all")
    run.add_argument("--mode", choices=("boundary", "mid"), default="boundary")
    run.add_argument("--jobs", type=int, default=1)
    return parser


def _run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.adapter not in ADAPTERS:
        parser.error(f"unknown adapter {args.adapter!r}; known: {', '.join(sorted(ADAPTERS))}")
    try:
        workload = get_workload(args.workload)
    except (KeyError, ValueError) as exc:
        parser.error(str(exc))
    if args.jobs < 1:
        parser.error("--jobs must be at least 1")
    points = [args.kill_at] if args.kill_at is not None else None
    with tempfile.TemporaryDirectory(prefix="revenant-") as root:
        result = sweep(
            ADAPTERS[args.adapter], workload, root,
            mode=args.mode, boundaries=points, jobs=args.jobs,
        )  # fmt: skip
    print(summary_line(result))
    return 0 if result.passed else 1


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return _run(args, parser)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
