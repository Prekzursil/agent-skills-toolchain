#!/usr/bin/env python3
"""Parser enumeration, null-stdin runner, and hang bound for TST-0248."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CLI = HERE / "operator_cli.py"
PLANTED = HERE / "fixtures" / "prompting_hang.py"
PY = sys.executable

# Wall-clock bound: no live command may wait on stdin. Loose vs CLI work,
# tight vs a human prompt.
HANG_BOUND_S = 2.0
PLANTED_TIMEOUT_S = 0.7


def rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def commands_from_parser(parser: argparse.ArgumentParser) -> list[str]:
    names: list[str] = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            names.extend(sorted(action.choices.keys()))
    if not names:
        raise RuntimeError("parser has no subcommands; enumeration is empty")
    return names


def subparser_map(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    return {}


def extras_from_subparser(sub: argparse.ArgumentParser) -> list[str]:
    extras: list[str] = []
    for action in sub._actions:
        if isinstance(action, argparse._HelpAction):
            continue
        if isinstance(action, (argparse._StoreTrueAction, argparse._StoreFalseAction)):
            if action.option_strings:
                extras.append(action.option_strings[0])
            continue
        if isinstance(action, argparse._CountAction):
            continue
        if action.option_strings and action.option_strings[0].startswith("-"):
            if action.nargs == 0:
                extras.append(action.option_strings[0])
            else:
                extras.extend([action.option_strings[0], "fixture-value"])
    return extras


def invocations_from_parser(parser: argparse.ArgumentParser) -> list[dict[str, Any]]:
    """Argv recipes from the live parser, not from documentation."""
    rows: list[dict[str, Any]] = [
        {"id": "root-help", "argv": ["--help"], "kind": "help", "command": None}
    ]
    subs = subparser_map(parser)
    for name in sorted(subs):
        sub = subs[name]
        rows.append(
            {
                "id": f"{name}-help",
                "argv": [name, "--help"],
                "kind": "help",
                "command": name,
            }
        )
        rows.append(
            {
                "id": f"{name}-bare",
                "argv": [name],
                "kind": "bare",
                "command": name,
            }
        )
        extra = extras_from_subparser(sub)
        if extra:
            rows.append(
                {
                    "id": f"{name}-filled",
                    "argv": [name] + extra,
                    "kind": "filled",
                    "command": name,
                }
            )
    return rows


def run_null_stdin(argv: list[str], timeout: float) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            argv,
            cwd=str(REPO),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            env=env,
            text=True,
        )
        elapsed = time.monotonic() - t0
        return {
            "argv": argv,
            "returncode": proc.returncode,
            "elapsed_s": round(elapsed, 6),
            "timed_out": False,
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
        }
    except subprocess.TimeoutExpired as exc:
        elapsed = time.monotonic() - t0
        stdout = (
            exc.stdout.decode("utf-8", "replace")
            if isinstance(exc.stdout, bytes)
            else (exc.stdout or "")
        )
        stderr = (
            exc.stderr.decode("utf-8", "replace")
            if isinstance(exc.stderr, bytes)
            else (exc.stderr or "")
        )
        return {
            "argv": argv,
            "returncode": 124,
            "elapsed_s": round(elapsed, 6),
            "timed_out": True,
            "stdout": stdout,
            "stderr": stderr,
        }


def combined(result: dict[str, Any]) -> str:
    return (result.get("stdout") or "") + (result.get("stderr") or "")


def is_actionable(text: str) -> bool:
    low = text.lower()
    has_what = "failed:" in low
    has_why = "why:" in low and ("stdin" in low or "tty" in low or "prompt" in low)
    has_next = "next:" in low
    return has_what and has_why and has_next


def expect_for(command: str | None, kind: str) -> str:
    if kind == "help":
        return "ok"
    if kind == "filled":
        return "ok"
    if command in {"confirm", "note"}:
        return "actionable-fail"
    if command is None:
        return "actionable-fail"
    return "ok"


def evaluate_row(row: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    kind = row["kind"]
    command = row.get("command")
    expect = expect_for(command, kind)
    text = combined(result)
    timed_out = bool(result["timed_out"])
    elapsed = float(result["elapsed_s"])
    rc = int(result["returncode"])
    under_bound = (not timed_out) and elapsed < HANG_BOUND_S
    ok = False
    reason = ""
    if timed_out or elapsed >= HANG_BOUND_S:
        reason = f"hung-or-slow elapsed={elapsed} timed_out={timed_out}"
    elif expect == "ok":
        ok = rc == 0
        reason = "ok" if ok else f"expected-exit-0 got={rc}"
    elif expect == "actionable-fail":
        ok = rc != 0 and is_actionable(text)
        reason = (
            "actionable-fail"
            if ok
            else f"expected-actionable-nonzero rc={rc} actionable={is_actionable(text)}"
        )
    return {
        "id": row["id"],
        "command": command,
        "kind": kind,
        "expect": expect,
        "argv": list(result["argv"][2:]),
        "returncode": rc,
        "elapsed_s": elapsed,
        "timed_out": timed_out,
        "under_hang_bound": under_bound,
        "actionable": is_actionable(text),
        "ok": bool(ok and under_bound),
        "reason": reason if not (ok and under_bound) else "pass",
        "stderr_tail": (result.get("stderr") or "")[-400:],
    }


def measure_cli() -> dict[str, Any]:
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    import operator_cli as cli  # noqa: E402

    parser = cli.build_parser()
    names = commands_from_parser(parser)
    recipes = invocations_from_parser(parser)
    covered = {r["command"] for r in recipes if r.get("command")}
    missing = [n for n in names if n not in covered]
    rows = []
    for recipe in recipes:
        argv = [PY, "-B", str(CLI), *recipe["argv"]]
        raw = run_null_stdin(argv, HANG_BOUND_S)
        rows.append(evaluate_row(recipe, raw))
    all_ok = all(r["ok"] for r in rows) and not missing
    max_elapsed = max((r["elapsed_s"] for r in rows), default=0.0)
    return {
        "enumerated_from": "argparse.ArgumentParser subparsers (live object, not docs)",
        "commands": names,
        "command_count": len(names),
        "missing_from_runs": missing,
        "invocations": rows,
        "all_ok": all_ok,
        "max_elapsed_s": round(max_elapsed, 6),
        "hang_bound_s": HANG_BOUND_S,
        "stdin": "subprocess.DEVNULL",
        "any_timed_out": any(r["timed_out"] for r in rows),
    }


def measure_hang_control() -> dict[str, Any]:
    planted = run_null_stdin([PY, "-B", str(PLANTED)], PLANTED_TIMEOUT_S)
    good = run_null_stdin([PY, "-B", str(CLI), "status"], HANG_BOUND_S)
    planted_caught = bool(planted["timed_out"]) and float(planted["elapsed_s"]) >= (
        PLANTED_TIMEOUT_S * 0.5
    )
    good_silent = (
        (not good["timed_out"])
        and good["returncode"] == 0
        and float(good["elapsed_s"]) < HANG_BOUND_S
    )
    return {
        "planted": {
            "path": rel(PLANTED),
            "timed_out": planted["timed_out"],
            "elapsed_s": planted["elapsed_s"],
            "returncode": planted["returncode"],
            "caught_by_hang_bound": planted_caught,
            "stderr_prefix": (planted.get("stderr") or "")[:80],
        },
        "good_status": {
            "timed_out": good["timed_out"],
            "elapsed_s": good["elapsed_s"],
            "returncode": good["returncode"],
            "silent_on_good_state": good_silent,
        },
        "planted_timeout_s": PLANTED_TIMEOUT_S,
        "hang_bound_s": HANG_BOUND_S,
        "pass": planted_caught and good_silent,
        "fired_on_bad_state": planted_caught,
        "silent_on_good_state": good_silent,
    }
