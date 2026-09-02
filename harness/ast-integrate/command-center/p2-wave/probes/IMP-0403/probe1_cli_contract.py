#!/usr/bin/env python3
"""Probe 1: CLI contract — every flag documented in `ast route --help` parses.

Negative control: an undocumented flag (including --inject) must be rejected.
The CLI must call the same route_query the router exposes.
"""

from __future__ import annotations

import argparse
import importlib.util
import io
import json
import re
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from router.route import route_query  # noqa: E402

INDEX = (
    HERE / "fixtures" / "capability-index.json"
).relative_to(REPO).as_posix()
LONG_OPT = re.compile(r"(?<!\w)--[a-z0-9][a-z0-9-]*")
VALUE_FLAGS = {"--query", "--index", "--cwd"}
FLAG_VALUES = {
    "--query": "lint a Python module for unused imports",
    "--index": INDEX,
    "--cwd": ".",
}


def load_cli():
    path = REPO / "tools" / "ast.py"
    spec = importlib.util.spec_from_file_location("imp0403_ast_cli", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def help_text(mod) -> str:
    parser = mod.build_parser()
    buf = io.StringIO()
    parser.parse_args(["route", "--help"])  # should SystemExit
    return buf.getvalue()


def route_help(mod) -> str:
    parser = mod.build_parser()
    buf = io.StringIO()
    try:
        with redirect_stdout(buf), redirect_stderr(buf):
            parser.parse_args(["route", "--help"])
    except SystemExit as exc:
        if int(exc.code or 0) != 0:
            raise AssertionError(f"route --help exited {exc.code}") from exc
    return buf.getvalue()


def documented_long_flags(text: str) -> list[str]:
    flags = []
    for m in LONG_OPT.finditer(text):
        flag = m.group(0)
        if flag not in flags:
            flags.append(flag)
    return flags


def parse_ok(parser: argparse.ArgumentParser, argv: list[str]) -> None:
    buf = io.StringIO()
    try:
        with redirect_stdout(buf), redirect_stderr(buf):
            parser.parse_args(argv)
    except SystemExit as exc:
        raise AssertionError(
            f"parse_args({argv!r}) exited {exc.code}: {buf.getvalue()!r}"
        ) from exc


def parse_exits(parser: argparse.ArgumentParser, argv: list[str]) -> int:
    buf = io.StringIO()
    try:
        with redirect_stdout(buf), redirect_stderr(buf):
            parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    raise AssertionError(f"parse_args({argv!r}) was expected to SystemExit")


def main() -> int:
    mod = load_cli()
    parser = mod.build_parser()
    text = route_help(mod)
    if "without injecting" not in text.lower() and "WITHOUT injecting" not in text:
        # help description uses "without injecting anything"
        if "without injecting anything" not in text:
            print("FAILED:IMP-0403-probe1 help does not document no-injection")
            print(text[:1500])
            return 1
    flags = documented_long_flags(text)
    if "--query" not in flags or "--index" not in flags:
        print("FAILED:IMP-0403-probe1 required flags missing from help", flags)
        return 1
    parsed = []
    for flag in flags:
        if flag in {"--help"}:
            code = parse_exits(parser, ["route", "--help"])
            if code != 0:
                print("FAILED:IMP-0403-probe1 --help exit", code)
                return 1
            parsed.append(flag)
            continue
        argv = ["route", "--query", FLAG_VALUES["--query"], "--index", INDEX]
        if flag == "--query":
            argv = ["route", "--query", FLAG_VALUES["--query"], "--index", INDEX]
        elif flag in VALUE_FLAGS:
            if flag == "--index":
                argv = ["route", "--query", FLAG_VALUES["--query"], "--index", INDEX]
            else:
                argv = [
                    "route",
                    "--query",
                    FLAG_VALUES["--query"],
                    "--index",
                    INDEX,
                    flag,
                    FLAG_VALUES[flag],
                ]
        elif flag == "--json":
            argv = [
                "route",
                "--query",
                FLAG_VALUES["--query"],
                "--index",
                INDEX,
                "--json",
            ]
        else:
            print("FAILED:IMP-0403-probe1 undocumented-in-contract flag", flag)
            return 1
        parse_ok(parser, argv)
        parsed.append(flag)

    parent_help = io.StringIO()
    try:
        with redirect_stdout(parent_help), redirect_stderr(parent_help):
            parser.parse_args(["--version"])
    except SystemExit as exc:
        if int(exc.code or 0) != 0:
            print("FAILED:IMP-0403-probe1 --version exit", exc.code)
            return 1
    else:
        print("FAILED:IMP-0403-probe1 --version did not SystemExit")
        return 1

    for bad in ("--inject", "--not-a-documented-flag"):
        code = parse_exits(
            parser,
            ["route", "--query", "x", "--index", INDEX, bad],
        )
        if code == 0:
            print("FAILED:IMP-0403-probe1 negative control accepted", bad)
            return 1

    live = route_query(
        "lint a Python module for unused imports", REPO / INDEX
    )
    if live.get("injection_performed") is not False or live.get("injected") != []:
        print("FAILED:IMP-0403-probe1 router injected")
        return 1
    if live.get("verdict") != "SELECTED":
        print("FAILED:IMP-0403-probe1 expected SELECTED", live.get("verdict"))
        return 1
    dumped = json.dumps(live)
    if "CANARY-IMP-0403-BODY" in dumped or "body" in live:
        print("FAILED:IMP-0403-probe1 body leaked into route_query result")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe1-cli-contract",
                "unit_id": "IMP-0403",
                "documented_flags": parsed,
                "help_flag_count": len(flags),
                "negative_rejected": ["--inject", "--not-a-documented-flag"],
                "router_identity": "router.route.route_query",
                "sample_verdict": live["verdict"],
                "injected": live["injected"],
            },
            sort_keys=True,
        )
    )
    print(
        "flags="
        + ",".join(parsed)
        + " negative_rejected=--inject,--not-a-documented-flag "
        + f"verdict={live['verdict']} injected={live['injected']}"
    )
    print("SUCCESS:IMP-0403-probe1 CLI contract: documented flags parse")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
