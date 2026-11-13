"""Command-line entry point.

Exit codes: 0 conformance passed (including pass with unconfirmed effects),
1 conformance failed, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from revenant import __version__
from revenant.adapters.mutant_checkpoint_first import CheckpointFirstMutant
from revenant.adapters.mutant_inplace import InPlaceMutant
from revenant.adapters.mutant_nocheckpoint import NoCheckpointMutant
from revenant.adapters.mutant_noledger import NoLedgerMutant
from revenant.adapters.mutant_volatile import VolatileMutant
from revenant.adapters.reference import ReferenceAdapter
from revenant.report import json_report, markdown_from_dict, summary_line
from revenant.runner import AdapterFactory, sweep
from revenant.workloads import WORKLOAD_NAMES, get_workload

ADAPTERS: dict[str, AdapterFactory] = {
    cls.name: cls
    for cls in (
        ReferenceAdapter,
        NoCheckpointMutant,
        InPlaceMutant,
        CheckpointFirstMutant,
        NoLedgerMutant,
        VolatileMutant,
    )
}


def _argv_for(adapter: str, workload: str) -> Callable[[Path], list[str]]:
    """Child command builder: every adapter name is also its module under ``revenant.adapters``."""

    def build(workdir: Path) -> list[str]:
        return [
            sys.executable, "-m", f"revenant.adapters.{adapter}",
            "--workload", workload, "--workdir", str(workdir),
        ]  # fmt: skip

    return build


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
    run.add_argument("--out", default=None, help="write the JSON report to this path")
    sub.add_parser("list", help="show known adapters and workloads")
    report = sub.add_parser("report", help="render a saved JSON report")
    report.add_argument("path")
    report.add_argument("--format", choices=("text", "md", "json"), default="text")
    return parser


def _report(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        with open(args.path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        parser.error(f"cannot read report {args.path!r}: {exc}")
    if not isinstance(data, dict) or "boundaries" not in data or "summary" not in data:
        parser.error(f"{args.path!r} is not a revenant report")
    if args.format == "text":
        sys.stdout.write(f"{data['summary']}\n")
    elif args.format == "md":
        sys.stdout.write(markdown_from_dict(data))
    else:
        sys.stdout.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
    return 0 if data.get("verdict") != "FAIL" else 1


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
            argv_for=_argv_for(args.adapter, args.workload),
        )  # fmt: skip
    if args.out:
        planned = len(points) if points is not None else None
        try:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(json_report(result, planned))
        except OSError as exc:
            parser.error(f"cannot write {args.out!r}: {exc}")
    print(summary_line(result))
    return 0 if result.passed else 1


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return _run(args, parser)
    if args.command == "list":
        print("adapters:  " + ", ".join(sorted(ADAPTERS)))
        print("workloads: " + ", ".join(WORKLOAD_NAMES))
        return 0
    if args.command == "report":
        return _report(args, parser)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
