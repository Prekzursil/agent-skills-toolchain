#!/usr/bin/env python3
"""AUD-0035: executable test that the decision log is reconciled.

PASS only when 17-DECISION-LOG.md exists, carries at least one 'MECH' token,
and line 175 does not assert the 31-way M-NN option-id collision as a live
present-tense blocker (Queued as P2-09 / remains live).

FAIL on the current unreconciled state: missing log, or zero MECH tokens with
line 175 still stating the collision in the present tense.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "AUD-0035"
LIVE_REL_CANDIDATES = (
    "17-DECISION-LOG.md",
    "command-center/17-DECISION-LOG.md",
    "docs/17-DECISION-LOG.md",
    "platform/corpus/17-DECISION-LOG.md",
)
LINE_NO = 175
STALE_LINE = (
    "The 31-way M-NN option-id collision between 07-OPTION-UNIVERSE family M "
    "and 13-ARCHITECTURE-CANDIDATES remains live. Queued as P2-09."
)
RECONCILED_LINE = (
    "The 31-way M-NN option-id collision between 07-OPTION-UNIVERSE family M "
    "and 13-ARCHITECTURE-CANDIDATES was re-prefixed to MECH-NN on 2026-08-07 "
    "at 18:41; the live shared-id count is 0. P2-09 is closed/superseded."
)
OPEN_QUEUE = "Queued as P2-09"
REMAINS_LIVE = "remains live"
CLOSED = re.compile(r"(?i)\b(closed|superseded|done)\b")


def repo_root() -> Path:
    return REPO


def live_log_path(root: Path | None = None) -> Path | None:
    env = (os.environ.get("AUD0035_DECISION_LOG") or "").strip()
    base = root or REPO
    if env:
        p = Path(env)
        if not p.is_absolute():
            p = base / env
        return p
    for rel in LIVE_REL_CANDIDATES:
        p = base / rel
        if p.is_file():
            return p
    return base / LIVE_REL_CANDIDATES[0]


def live_log_present(root: Path | None = None) -> bool:
    env = (os.environ.get("AUD0035_DECISION_LOG") or "").strip()
    if env:
        p = Path(env)
        if not p.is_absolute():
            p = (root or REPO) / env
        return p.is_file()
    base = root or REPO
    return any((base / rel).is_file() for rel in LIVE_REL_CANDIDATES)


def stale_lines() -> list[str]:
    lines = [
        "# 17-DECISION-LOG (unreconciled capture of the documented blocker)",
        "",
        "Release mode is PR-ONLY.",
    ]
    while len(lines) < LINE_NO - 1:
        n = len(lines) + 1
        lines.append(f"- entry {n}: operational note; no option-id claim.")
    lines.append(STALE_LINE)
    text = "\n".join(lines)
    if "MECH" in text:
        raise RuntimeError("stale capture must not contain MECH tokens")
    if len(lines) != LINE_NO:
        raise RuntimeError(f"stale capture must have exactly {LINE_NO} lines")
    return lines


def stale_text() -> str:
    return "\n".join(stale_lines()) + "\n"


def fixture_path() -> Path:
    return HERE / "fixtures" / "stale-decision-log.md"


def write_stale_fixture() -> Path:
    path = fixture_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stale_text(), encoding="utf-8", newline="\n")
    return path


def mech_token_count(text: str) -> int:
    return text.count("MECH")


def present_tense_collision(line: str) -> bool:
    if "collision" not in line.lower():
        return False
    if REMAINS_LIVE in line:
        return True
    if OPEN_QUEUE in line and not CLOSED.search(line):
        return True
    return False


def evaluate(path: Path) -> dict:
    rel = path.as_posix()
    try:
        rel = path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        rel = str(path)
    if not path.is_file():
        msg = (
            f"FAIL: {rel} is absent (unreconciled). Catalog blocker is "
            f"{LIVE_REL_CANDIDATES[0]}:{LINE_NO} present-tense M-NN collision "
            "with zero MECH tokens."
        )
        return {
            "ok": False,
            "color": "RED",
            "exit_code": 1,
            "assertion": msg,
            "path": rel,
            "exists": False,
            "line_count": 0,
            "line_175": None,
            "mech_token_count": 0,
            "present_tense_collision": False,
        }
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    line = lines[LINE_NO - 1] if len(lines) >= LINE_NO else ""
    mech = mech_token_count(text)
    live_collision = present_tense_collision(line) if line else False
    if len(lines) < LINE_NO:
        msg = (
            f"FAIL: {rel} has {len(lines)} lines; line {LINE_NO} is missing "
            "so the log is not a reconciled MECH-NN record."
        )
        return {
            "ok": False,
            "color": "RED",
            "exit_code": 1,
            "assertion": msg,
            "path": rel,
            "exists": True,
            "line_count": len(lines),
            "line_175": None,
            "mech_token_count": mech,
            "present_tense_collision": False,
        }
    if mech == 0 and live_collision:
        msg = (
            f"FAIL: {rel} has 0 MECH tokens; line {LINE_NO} still states the "
            f"M-NN option-id collision in the present tense: {line}"
        )
        return {
            "ok": False,
            "color": "RED",
            "exit_code": 1,
            "assertion": msg,
            "path": rel,
            "exists": True,
            "line_count": len(lines),
            "line_175": line,
            "mech_token_count": mech,
            "present_tense_collision": True,
        }
    if mech == 0:
        msg = (
            f"FAIL: {rel} carries zero MECH tokens; decision log is not "
            "reconciled to the MECH-NN namespace."
        )
        return {
            "ok": False,
            "color": "RED",
            "exit_code": 1,
            "assertion": msg,
            "path": rel,
            "exists": True,
            "line_count": len(lines),
            "line_175": line,
            "mech_token_count": mech,
            "present_tense_collision": live_collision,
        }
    if live_collision:
        msg = (
            f"FAIL: {rel} line {LINE_NO} still states the M-NN option-id "
            f"collision in the present tense: {line}"
        )
        return {
            "ok": False,
            "color": "RED",
            "exit_code": 1,
            "assertion": msg,
            "path": rel,
            "exists": True,
            "line_count": len(lines),
            "line_175": line,
            "mech_token_count": mech,
            "present_tense_collision": True,
        }
    msg = (
        f"PASS: {rel} is reconciled ({mech} MECH tokens; line {LINE_NO} is "
        "not a present-tense live collision)."
    )
    return {
        "ok": True,
        "color": "GREEN",
        "exit_code": 0,
        "assertion": msg,
        "path": rel,
        "exists": True,
        "line_count": len(lines),
        "line_175": line,
        "mech_token_count": mech,
        "present_tense_collision": False,
    }


def reconcile_text(text: str) -> str:
    if not (text or "").strip():
        lines = stale_lines()
    else:
        lines = text.splitlines()
        while len(lines) < LINE_NO:
            n = len(lines) + 1
            lines.append(f"- entry {n}: operational note; no option-id claim.")
    lines[LINE_NO - 1] = RECONCILED_LINE
    out = "\n".join(lines) + "\n"
    if "MECH" not in out:
        raise RuntimeError("reconcile_text must introduce MECH tokens")
    if present_tense_collision(lines[LINE_NO - 1]):
        raise RuntimeError("reconcile_text left a present-tense collision")
    return out


def write_reconciled_copy(src: Path | None, dest: Path) -> Path:
    if src is not None and src.is_file():
        text = src.read_text(encoding="utf-8")
    else:
        text = stale_text()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(reconcile_text(text), encoding="utf-8", newline="\n")
    return dest


def write_unreconciled_copy(dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(stale_text(), encoding="utf-8", newline="\n")
    return dest


def current_tree_subject(root: Path | None = None) -> tuple[Path, str]:
    """Path the failing test runs against for 'current tree'.

    Prefer the live 17-DECISION-LOG.md. This Linux worktree omits that file;
    the catalog documents the live blocker as line 175 present-tense collision
    with zero MECH tokens, so the captured stale fixture is the current-state
    subject when the live path is absent.
    """
    live = live_log_path(root)
    if live is not None and live.is_file():
        return live, "live"
    fixture = write_stale_fixture()
    return fixture, "captured-stale-fixture"


def format_cli(result: dict) -> str:
    return json.dumps(
        {
            "ok": result["ok"],
            "color": result["color"],
            "exit_code": result["exit_code"],
            "assertion": result["assertion"],
            "path": result["path"],
            "exists": result["exists"],
            "line_count": result["line_count"],
            "line_175": result["line_175"],
            "mech_token_count": result["mech_token_count"],
            "present_tense_collision": result["present_tense_collision"],
        },
        sort_keys=True,
    )


def run_cli(argv: list[str]) -> int:
    if argv:
        path = Path(argv[0])
        if not path.is_absolute():
            path = REPO / path
    else:
        path, _kind = current_tree_subject()
    result = evaluate(path)
    print(format_cli(result))
    print(result["assertion"])
    if result["ok"]:
        print(f"SUCCESS:{UNIT}-test reconciled")
        return 0
    print(f"RED:{UNIT}-test unreconciled")
    return 1
