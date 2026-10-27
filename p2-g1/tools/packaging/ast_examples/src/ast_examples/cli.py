"""ast-examples CLI. Invoked as `ast-examples run --id <id> --profile <dir>`."""
from __future__ import annotations

import argparse
import sys

from ast_examples.runner import run_example


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = list(sys.argv[1:])
    parser = argparse.ArgumentParser(prog="ast-examples")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run_p = sub.add_parser("run")
    run_p.add_argument("--id", required=True)
    run_p.add_argument("--profile", required=True)
    args = parser.parse_args(argv)
    if args.cmd != "run":
        parser.error("unknown command")
    return run_example(args.id, args.profile)


if __name__ == "__main__":
    raise SystemExit(main())
