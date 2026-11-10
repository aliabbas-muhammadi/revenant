"""Command-line entry point. Subcommands are added as the harness grows (see ROADMAP.md)."""

import argparse

from revenant import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="revenant", description=__doc__)
    parser.add_argument("--version", action="version", version=f"revenant {__version__}")
    parser.parse_args(argv)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
