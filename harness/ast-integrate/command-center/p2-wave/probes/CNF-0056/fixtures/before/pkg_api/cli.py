"""CLI tree for the before-state fixture (argparse subcommands)."""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pkg-api")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("alpha", help="alpha command")
    sub.add_parser("beta", help="beta command")
    sub.add_parser("legacy", help="legacy command")
    return parser


def main(argv: list[str] | None = None) -> int:
    build_parser().parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
