#!/usr/bin/env python3
"""CLI / SDK / structured-builder surfaces sharing one builder core.

CLI never prints a traceback for invalid specs: it prints path-named
ERROR lines and exits 2. SDK returns typed dicts, not strings-as-truth.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import builder as B  # noqa: E402
import spec as S  # noqa: E402

EXIT_OK = 0
EXIT_INVALID = 2
EXIT_USAGE = 64


def sdk_build(goal: str) -> dict[str, Any]:
    return B.build_from_goal(goal, surface="sdk")


def sdk_validate(document: Any) -> dict[str, Any]:
    errs = S.validate(document)
    return {
        "ok": not errs,
        "errors": errs,
        "formatted": S.format_errors(errs),
    }


def builder_answers(answers: dict[str, Any]) -> dict[str, Any]:
    return B.build_from_answers(answers, surface="builder")


def canonical(spec: dict[str, Any]) -> str:
    body = {k: v for k, v in spec.items() if k != "source_surface"}
    return json.dumps(body, indent=2, sort_keys=True)


def _print_build(result: dict[str, Any]) -> int:
    if result.get("ok"):
        print(json.dumps(result["spec"], indent=2, sort_keys=True))
        print("---")
        print(result.get("restatement") or S.restatement(result["spec"]))
        return EXIT_OK
    formatted = S.format_errors(result.get("errors") or [])
    print(formatted or "ERROR /: invalid-spec")
    return EXIT_INVALID


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="council-surface")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_build = sub.add_parser("build", help="CLI: build a CouncilSpec from a goal phrase")
    p_build.add_argument("--goal", default=None)
    p_build.add_argument("--goal-id", default=None)

    p_val = sub.add_parser("validate", help="CLI: validate a CouncilSpec JSON file")
    p_val.add_argument("--file", required=True)

    p_sb = sub.add_parser("structured-build", help="typed builder from goal_id")
    p_sb.add_argument("--goal-id", required=True)

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else EXIT_USAGE
        return code

    try:
        if args.cmd == "build":
            text = args.goal_id or args.goal
            if not text:
                print("ERROR /natural_language: required: provide --goal or --goal-id")
                return EXIT_INVALID
            return _print_build(B.build_from_goal(text, surface="cli"))
        if args.cmd == "structured-build":
            return _print_build(B.build_from_answers({"goal_id": args.goal_id}, surface="builder"))
        if args.cmd == "validate":
            path = Path(args.file)
            try:
                raw = path.read_text(encoding="utf-8")
                doc = json.loads(raw)
            except FileNotFoundError:
                print(f"ERROR /: missing-file: {path}")
                return EXIT_INVALID
            except json.JSONDecodeError as exc:
                print(f"ERROR /: parse-error: JSON {exc.msg} at line {exc.lineno}")
                return EXIT_INVALID
            result = sdk_validate(doc)
            if result["ok"]:
                print("VALID")
                return EXIT_OK
            print(result["formatted"])
            return EXIT_INVALID
        print("ERROR /: usage")
        return EXIT_USAGE
    except Exception as exc:
        # Last-resort: still a path-named line, never a traceback dump.
        print(f"ERROR /: internal-caught: {type(exc).__name__}: {exc}")
        return EXIT_INVALID


if __name__ == "__main__":
    raise SystemExit(main())
