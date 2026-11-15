"""Command-line entry point.

Exit codes: 0 conformance passed (including pass with unconfirmed effects),
1 conformance failed, 2 usage error.
"""

from __future__ import annotations

import argparse
import contextlib
import functools
import json
import logging
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
from revenant.adapters.reference_sqlite import SqliteOutboxAdapter, SqliteReferenceAdapter
from revenant.chaos import CHAOS_MODES
from revenant.report import json_report, markdown_from_dict, summary_line
from revenant.runner import AdapterFactory, UnsupportedPlatform, require_sigkill, sweep
from revenant.workloads import WORKLOAD_NAMES, get_workload

ADAPTERS: dict[str, AdapterFactory] = {
    cls.name: cls
    for cls in (
        ReferenceAdapter,
        SqliteReferenceAdapter,
        SqliteOutboxAdapter,
        NoCheckpointMutant,
        InPlaceMutant,
        CheckpointFirstMutant,
        NoLedgerMutant,
        VolatileMutant,
    )
}


try:  # the LangGraph adapter needs the optional ``langgraph`` extra
    from revenant.adapters.langgraph_sqlite import LangGraphAdapter

    ADAPTERS[LangGraphAdapter.name] = LangGraphAdapter
except ImportError:
    pass


def _argv_for(
    adapter: str, workload: str, extra: tuple[str, ...] = ()
) -> Callable[[Path], list[str]]:
    """Child command builder: every adapter name is also its module under ``revenant.adapters``."""

    def build(workdir: Path) -> list[str]:
        return [
            sys.executable, "-m", f"revenant.adapters.{adapter}",
            "--workload", workload, "--workdir", str(workdir), *extra,
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
    run.add_argument("--naive-tools", action="store_true",
                     help="langgraph_sqlite only: bypass the effects ledger")  # fmt: skip
    run.add_argument("--chaos", choices=CHAOS_MODES, default="none",
                     help="inject faults (reference-based adapters only)")  # fmt: skip
    run.add_argument("--keep-workdirs", action="store_true",
                     help="keep workdirs and print where")  # fmt: skip
    run.add_argument("--verbose", action="store_true", help="log progress to stderr")
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


def _enable_logging() -> None:
    """Send the package's progress logs to stderr."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    package = logging.getLogger("revenant")
    package.addHandler(handler)
    package.setLevel(logging.INFO)


def _run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.adapter not in ADAPTERS:
        parser.error(f"unknown adapter {args.adapter!r}; known: {', '.join(sorted(ADAPTERS))}")
    try:
        workload = get_workload(args.workload)
    except (KeyError, ValueError) as exc:
        parser.error(str(exc))
    if args.jobs < 1:
        parser.error("--jobs must be at least 1")
    try:
        require_sigkill()
    except UnsupportedPlatform as exc:
        parser.error(str(exc))
    factory = ADAPTERS[args.adapter]
    extra: tuple[str, ...] = ()
    if args.naive_tools:
        if args.adapter != "langgraph_sqlite":
            parser.error("--naive-tools only applies to --adapter langgraph_sqlite")
        factory = functools.partial(LangGraphAdapter, naive_tools=True)
        extra = ("--naive-tools",)
    is_reference = isinstance(factory, type) and issubclass(factory, ReferenceAdapter)
    if args.chaos != "none" and not is_reference:
        parser.error("--chaos only applies to adapters built on the reference runtime")
    if args.verbose:
        _enable_logging()
    if args.kill_at is not None:
        with tempfile.TemporaryDirectory(prefix="revenant-probe-") as probe:
            adapter = factory()
            adapter.build(workload, probe)
            count = adapter.boundaries()
        if not 1 <= args.kill_at <= count:
            parser.error(f"--kill-at {args.kill_at} is out of range; valid boundaries: 1..{count}")
    points = [args.kill_at] if args.kill_at is not None else None
    with contextlib.ExitStack() as stack:
        if args.keep_workdirs:
            root = tempfile.mkdtemp(prefix="revenant-")
            print(f"workdirs kept in {root}", file=sys.stderr)
        else:
            root = stack.enter_context(tempfile.TemporaryDirectory(prefix="revenant-"))
        result = sweep(
            factory, workload, root,
            mode=args.mode, boundaries=points, jobs=args.jobs, chaos=args.chaos,
            argv_for=_argv_for(args.adapter, args.workload, extra),
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
