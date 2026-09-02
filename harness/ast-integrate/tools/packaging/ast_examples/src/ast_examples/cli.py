"""ast-examples CLI.

    ast-examples catalog                      list the example ids (exit 0)
    ast-examples run --id <id> [--profile <dir>] produce one example artifact

``--profile`` falls back to ``$AST_EXAMPLES_PROFILE`` and then to the current
directory, so the quick-start's ``ast-examples run --id quickstart-hello`` works
verbatim from inside a clean profile.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from ast_examples.runner import catalog, run_example


def default_profile() -> str:
    return os.environ.get("AST_EXAMPLES_PROFILE") or os.getcwd()


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = list(sys.argv[1:])
    parser = argparse.ArgumentParser(prog="ast-examples")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run_p = sub.add_parser("run", help="produce one documented example artifact")
    run_p.add_argument("--id", required=True)
    run_p.add_argument(
        "--profile",
        default=None,
        help="profile directory (default: $AST_EXAMPLES_PROFILE, then the current directory)",
    )
    cat_p = sub.add_parser("catalog", help="list every example id this package can produce")
    cat_p.add_argument("--json", action="store_true", help="emit the catalog as JSON")
    args = parser.parse_args(argv)
    if args.cmd == "catalog":
        rows = catalog()
        if args.json:
            print(json.dumps({"examples": rows}, indent=2, sort_keys=True))
        else:
            for row in rows:
                print(f"{row['id']}\t{row['artifact']}")
        return 0
    if args.cmd != "run":
        parser.error("unknown command")
    return run_example(args.id, args.profile or default_profile())


if __name__ == "__main__":
    raise SystemExit(main())
