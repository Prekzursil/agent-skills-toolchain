#!/usr/bin/env python3
"""A8 one-command product surface — executable subject for ARC-0057.

This is not an A8 DESIGN rebuild. It is the tiny job-oriented CLI the test
plan specifies: one command, three verbs (jobs, catalog, cockpit), and one
error contract (happened / means / next_action).
"""
from __future__ import annotations

import argparse
import json
import sys

JOBS = [
    "discover a workflow from the catalog",
    "run the one command for an owner job",
    "read cockpit status in a plain, non-visual form",
]


def emit_error(happened: str, means: str, next_action: str) -> int:
    print(f"happened: {happened}")
    print(f"means: {means}")
    print(f"next_action: {next_action}")
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="a8_product.py",
        description="A8 one-command surface (jobs / catalog / cockpit).",
    )
    sub = parser.add_subparsers(dest="verb")

    sub.add_parser("jobs", help="list the owner jobs this command covers")

    p_cat = sub.add_parser("catalog", help="list the product catalog")
    # DOCUMENTED-FLAG-FORMAT
    p_cat.add_argument("--format", choices=("text", "json"), default="text")

    p_cock = sub.add_parser("cockpit", help="owner cockpit")
    p_cock.add_argument("--plain", action="store_true", help="screen-reader / no CSI")
    p_cock.add_argument("--visual", action="store_true", help="visual TUI (absent here)")

    args = parser.parse_args(argv)
    if not args.verb:
        parser.print_help()
        return 0
    if args.verb == "jobs":
        for job in JOBS:
            print(f"- {job}")
        return 0
    if args.verb == "catalog":
        entries = ["jobs", "catalog", "cockpit"]
        if args.format == "json":
            print(json.dumps({"surface": "catalog", "format": "json", "entries": entries}))
        else:
            print("catalog: " + ", ".join(entries))
        return 0
    if args.verb == "cockpit":
        if args.visual and not args.plain:
            return emit_error(
                "visual cockpit requested",
                "this Linux worktree has no visual cockpit surface",
                "re-run with --plain, or skip this documented command as NOT-CHECKED",
            )
        # plain (default) — no CSI / cursor addressing
        print("cockpit status: ready")
        print("jobs: 3")
        print("next_action: pick a job from `a8_product.py jobs`")
        return 0
    return emit_error(
        f"unknown verb {args.verb!r}",
        "the one-command surface does not recognize that job",
        "run a8_product.py --help and pick jobs, catalog, or cockpit",
    )


if __name__ == "__main__":
    raise SystemExit(main())
