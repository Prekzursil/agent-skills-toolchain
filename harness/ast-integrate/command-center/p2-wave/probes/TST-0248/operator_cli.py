#!/usr/bin/env python3
"""Operator CLI surface for TST-0248 (non-interactive stdin contract).

Production monitorcore.unified is not on this worktree. This parser is the live
CLI under test: every subcommand is defined here and enumerated from argparse,
never from a markdown table.

Contract: never call input()/read stdin. Missing required values fail closed
with what / why / next-command. Cursor addressing is not emitted.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

PROG = "operator_cli.py"


def stdin_is_interactive() -> bool:
    try:
        return bool(sys.stdin.isatty())
    except Exception:
        return False


def actionable_fail(what: str, why: str, next_cmd: str) -> int:
    print(f"FAILED:{what}", file=sys.stderr)
    print(f"why: {why}", file=sys.stderr)
    print(f"Next: {next_cmd}", file=sys.stderr)
    return 2


def pane_fields() -> dict:
    return {
        "unit": "TST-0248",
        "mode": "non-interactive",
        "panes": [
            {"id": "status", "title": "Status", "value": "idle"},
            {"id": "jobs", "title": "Jobs", "value": "0"},
            {"id": "errors", "title": "Errors", "value": "0"},
        ],
        "stdin_interactive": stdin_is_interactive(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Operator cockpit non-interactive surface",
        add_help=True,
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="line-oriented output; no cursor addressing",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    sub.add_parser("status", help="print operator status fields")
    sub.add_parser("panes", help="list cockpit pane identifiers")
    sub.add_parser("plain", help="dump the same field set as line-oriented text")
    sub.add_parser("version", help="print CLI version")

    p_confirm = sub.add_parser(
        "confirm",
        help="acknowledge an action; never prompts (requires --yes)",
    )
    p_confirm.add_argument(
        "--yes",
        action="store_true",
        help="required acknowledgement; absence must not prompt",
    )

    p_note = sub.add_parser(
        "note",
        help="record a note; never reads stdin (requires --text)",
    )
    p_note.add_argument(
        "--text",
        default=None,
        help="note body; required in non-interactive use",
    )
    return parser


def render(fields: dict, *, plain: bool) -> str:
    if plain:
        lines = [
            f"unit={fields['unit']}",
            f"mode={fields['mode']}",
            f"stdin_interactive={fields['stdin_interactive']}",
        ]
        for pane in fields["panes"]:
            lines.append(f"pane.{pane['id']}={pane['value']}")
        return "\n".join(lines) + "\n"
    return json.dumps(fields, sort_keys=True) + "\n"


def dispatch(args: argparse.Namespace) -> int:
    plain = bool(getattr(args, "plain", False) or args.command == "plain")
    why_null = (
        "stdin is not a TTY (attached to the null device or a pipe); "
        "this CLI never blocks on a prompt"
    )

    if not args.command:
        return actionable_fail(
            "missing command",
            why_null,
            f"python3 command-center/p2-wave/probes/TST-0248/{PROG} --help",
        )

    if args.command == "version":
        print("TST-0248-operator-cli 1.0.0")
        return 0

    if args.command in {"status", "panes", "plain"}:
        fields = pane_fields()
        if args.command == "panes" and not plain:
            print(json.dumps([p["id"] for p in fields["panes"]]))
            return 0
        sys.stdout.write(render(fields, plain=plain or args.command == "plain"))
        return 0

    if args.command == "confirm":
        if not args.yes:
            return actionable_fail(
                "confirm requires --yes",
                why_null,
                f"python3 command-center/p2-wave/probes/TST-0248/{PROG} confirm --yes",
            )
        print("CONFIRMED:yes")
        return 0

    if args.command == "note":
        text = args.text
        if text is None or text == "":
            return actionable_fail(
                "note requires --text",
                why_null,
                f"python3 command-center/p2-wave/probes/TST-0248/{PROG} note --text fixture-value",
            )
        print(f"NOTE:{text}")
        return 0

    return actionable_fail(
        f"unknown command {args.command!r}",
        why_null,
        f"python3 command-center/p2-wave/probes/TST-0248/{PROG} --help",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    return dispatch(args)


if __name__ == "__main__":
    raise SystemExit(main())
