#!/usr/bin/env python3
"""apply_closed_batch.py - ONE reversible apply-when-closed batch for the config flips.

APPLY-WHEN-CLOSED. ``~/.claude.json`` is rewritten by any LIVE Claude session every
~30s, so a hand edit made while Claude runs is clobbered within the minute. This tool
therefore REFUSES to write while a ``claude`` process is alive, writes a timestamped
backup before touching anything, and can restore that backup with ``--revert-from``.

It ships four independently selectable ops (``--only`` picks a subset)::

    serena-projects   drop "serena" from the per-project disabledMcpServers lists of
                      ONLY the scoped repos (default: agent-skills-toolchain, Reframe,
                      momentstudio, metaswarm). Every other project block is untouched.
    serena-root       drop "serena" from the ROOT disabledMcpServers list.
    grep              register the REMOTE-HTTP code-search server
                      {"type": "http", "url": "https://mcp.grep.app"} - remote HTTP
                      costs ZERO per-session stdio processes.
    playwright        append "--extension" to the playwright MCP argv.

Everything is additive and reversible: ops only DELETE the single string "serena" from
two list shapes, ADD one absent ``mcpServers`` key, and APPEND one argv flag. Nothing
else in the file is read, rewritten from scratch, or normalised - the untouched value
tree is carried through by ``copy.deepcopy`` and re-serialised verbatim. It never opens
``accounts.json`` or any credential store.

Read-only modes (``--list``, the default dry-run preview) are ALLOWED while Claude is
running - that is how you inspect before deciding. Only the WRITE paths (``--apply``,
``--revert-from``) are gated on the process check.

Examples::

    # what is the live state right now? (read-only, safe with Claude open)
    python apply_closed_batch.py --list

    # preview the batch (default; writes nothing)
    python apply_closed_batch.py

    # test the precedence question first: projects only, leave root alone
    python apply_closed_batch.py --only serena-projects --apply

    # the whole batch, for real, with Claude CLOSED
    python apply_closed_batch.py --apply

    # undo
    python apply_closed_batch.py --revert-from ~/.claude.json.bak-20260724-120000
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import subprocess  # nosemgrep: python-subprocess-audit -- fixed argv, no shell, no user input
import sys
import time
from typing import Any, Callable

DEFAULT_TARGET = os.path.expanduser("~/.claude.json")

#: Repos whose project blocks get serena re-enabled. A project key matches a repo when
#: one of its PATH SEGMENTS equals the marker (case-insensitively) - so "momentstudio"
#: matches ".../Downloads/momentstudio" but NOT ".../momentstudio-fix", which is a
#: different checkout. Widen deliberately with --extra-project, never by accident.
DEFAULT_SCOPED_REPOS = (
    "agent-skills-toolchain",
    "Reframe",
    "momentstudio",
    "metaswarm",
)

SERENA = "serena"
GREP_SERVER = "grep"
#: Remote HTTP transport => no per-session stdio child process (the freeze driver).
GREP_ENTRY = {"type": "http", "url": "https://mcp.grep.app"}
PLAYWRIGHT_SERVER = "playwright"
PLAYWRIGHT_FLAG = "--extension"

OP_NAMES = ("serena-projects", "serena-root", "grep", "playwright")

#: Process image names that mean "a Claude session is live". Matched against the image
#: NAME only, never the command line - a command line match would also fire on this
#: script's own argv when it is run from under a ".claude" directory (the classic
#: self-matching-probe defect).
CLAUDE_IMAGE_NAMES = ("claude", "claude.exe")


class Status:
    """Terminal states an op can report."""

    CHANGE = "WOULD-CHANGE"
    NOOP = "no-op (already applied)"
    NA = "n/a (nothing to act on)"
    CONFLICT = "CONFLICT (refusing to clobber)"


class OpResult:
    """One op's verdict plus the mutation that realises it."""

    def __init__(
        self,
        name: str,
        status: str,
        detail: list[str],
        mutate: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.name = name
        self.status = status
        self.detail = detail
        self.mutate = mutate

    @property
    def changes(self) -> bool:
        return self.status == Status.CHANGE


# --------------------------------------------------------------------------- probes


def _tasklist_names() -> list[str]:
    """Image names from the platform process table. Raises on any probe failure."""
    if os.name == "nt":
        out = subprocess.run(  # noqa: S603  # nosemgrep
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        ).stdout
        names = []
        for line in out.splitlines():
            line = line.strip()
            if not line.startswith('"'):
                continue
            names.append(line.split('","')[0].lstrip('"'))
        return names
    out = subprocess.run(  # noqa: S603  # nosemgrep
        ["ps", "-e", "-o", "comm="],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    ).stdout
    return [os.path.basename(line.strip()) for line in out.splitlines() if line.strip()]


def detect_claude(lister: Callable[[], list[str]] | None = None) -> list[str]:
    """Return the live Claude image names. Empty list => safe to write.

    FAILS CLOSED: if the process table cannot be read the caller must treat it as
    "Claude might be running", because a false "all clear" here costs the whole edit.

    An EMPTY CENSUS is a broken probe, not an idle machine, and must raise rather
    than read as "no Claude running". A real process table always contains at least
    the process doing the probing, so zero parsed rows means the platform command
    succeeded but produced nothing usable (blank stdout, an unexpected format, a
    localised header-only listing). Without this, `_guard` sees `[]`, returns 0, and
    an `--apply` writes the config out from under a LIVE session that rewrites
    ~/.claude.json every ~30s - exactly the clobber the guard exists to prevent.
    """
    names = (lister or _tasklist_names)()
    if not names:
        raise RuntimeError(
            "process census is EMPTY - the probe is broken, not the machine idle "
            "(this process is itself in the table). Refusing to read that as "
            "'no Claude running'."
        )
    return sorted({n.lower() for n in names if n.lower() in CLAUDE_IMAGE_NAMES})


# ------------------------------------------------------------------------ matching


def _segments(path_key: str) -> list[str]:
    return [seg for seg in path_key.replace("\\", "/").split("/") if seg]


def match_projects(config: dict[str, Any], repos: tuple[str, ...] | list[str]) -> dict:
    """Map repo marker -> the project keys it scopes to (exact path-SEGMENT match)."""
    wanted = {r.lower(): r for r in repos}
    hits: dict[str, list[str]] = {r: [] for r in repos}
    for key in config.get("projects", {}):
        for seg in _segments(key):
            repo = wanted.get(seg.lower())
            if repo is not None:
                hits[repo].append(key)
                break
    return {repo: sorted(keys) for repo, keys in hits.items()}


def near_misses(
    config: dict[str, Any], repos: tuple[str, ...] | list[str]
) -> list[str]:
    """Project keys that CONTAIN a marker but do not match it as a whole segment."""
    matched = {k for keys in match_projects(config, repos).values() for k in keys}
    lowered = [r.lower() for r in repos]
    out = []
    for key in config.get("projects", {}):
        if key in matched:
            continue
        low = key.replace("\\", "/").lower()
        if any(r in low for r in lowered):
            out.append(key)
    return sorted(out)


# ------------------------------------------------------------------------------ ops


def op_serena_projects(config: dict[str, Any], repos) -> OpResult:
    hits = match_projects(config, repos)
    targets = []
    detail = []
    for repo in repos:
        keys = hits[repo]
        if not keys:
            detail.append(f"    {repo}: 0 project blocks (nothing scoped here)")
            continue
        for key in keys:
            block = config["projects"][key]
            disabled = block.get("disabledMcpServers")
            if isinstance(disabled, list) and SERENA in disabled:
                targets.append(key)
                detail.append(f"    {repo}: {key}  -> drop {SERENA!r}")
            else:
                detail.append(f"    {repo}: {key}  (already enabled)")

    total = len(config.get("projects", {}))
    still = sum(
        1
        for k, v in config.get("projects", {}).items()
        if isinstance(v, dict)
        and SERENA in (v.get("disabledMcpServers") or [])
        and k not in targets
    )
    detail.append(f"    -> {len(targets)} of {total} project blocks touched")
    detail.append(f"    -> {still} project blocks KEEP serena disabled (untouched)")

    if not targets:
        return OpResult("serena-projects", Status.NA, detail)

    def mutate(cfg: dict[str, Any]) -> None:
        for key in targets:
            disabled = cfg["projects"][key]["disabledMcpServers"]
            cfg["projects"][key]["disabledMcpServers"] = [
                s for s in disabled if s != SERENA
            ]

    return OpResult("serena-projects", Status.CHANGE, detail, mutate)


def op_serena_root(config: dict[str, Any]) -> OpResult:
    disabled = config.get("disabledMcpServers")
    if not isinstance(disabled, list):
        return OpResult("serena-root", Status.NA, ["    no root disabledMcpServers"])
    if SERENA not in disabled:
        return OpResult(
            "serena-root", Status.NOOP, [f"    root list has no {SERENA!r} entry"]
        )
    detail = [
        f"    root disabledMcpServers: {len(disabled)} -> {len(disabled) - 1} entries",
        f"    drop {SERENA!r}; the other {len(disabled) - 1} stay in order",
    ]

    def mutate(cfg: dict[str, Any]) -> None:
        cfg["disabledMcpServers"] = [
            s for s in cfg["disabledMcpServers"] if s != SERENA
        ]

    return OpResult("serena-root", Status.CHANGE, detail, mutate)


def op_grep(config: dict[str, Any]) -> OpResult:
    servers = config.get("mcpServers")
    if not isinstance(servers, dict):
        return OpResult("grep", Status.NA, ["    no mcpServers map in target"])
    current = servers.get(GREP_SERVER)
    if current == GREP_ENTRY:
        return OpResult("grep", Status.NOOP, ["    already registered identically"])
    if current is not None:
        return OpResult(
            "grep",
            Status.CONFLICT,
            [
                f"    {GREP_SERVER!r} already exists with a DIFFERENT value:",
                f"      {json.dumps(current)}",
                "    refusing to clobber - remove it by hand first if you want ours",
            ],
        )
    detail = [f"    add mcpServers[{GREP_SERVER!r}] = {json.dumps(GREP_ENTRY)}"]

    def mutate(cfg: dict[str, Any]) -> None:
        cfg["mcpServers"][GREP_SERVER] = dict(GREP_ENTRY)

    return OpResult("grep", Status.CHANGE, detail, mutate)


def op_playwright(config: dict[str, Any]) -> OpResult:
    servers = config.get("mcpServers")
    if not isinstance(servers, dict) or PLAYWRIGHT_SERVER not in servers:
        return OpResult(
            "playwright", Status.NA, [f"    no {PLAYWRIGHT_SERVER!r} entry in target"]
        )
    entry = servers[PLAYWRIGHT_SERVER]
    if not isinstance(entry, dict) or not isinstance(entry.get("args"), list):
        return OpResult(
            "playwright",
            Status.CONFLICT,
            [
                "    entry has no args list; cannot append a flag safely:",
                f"      {json.dumps(entry)}",
            ],
        )
    args = entry["args"]
    if PLAYWRIGHT_FLAG in args:
        return OpResult(
            "playwright", Status.NOOP, [f"    args already carry {PLAYWRIGHT_FLAG}"]
        )
    detail = [
        f"    args {json.dumps(args)}",
        f"      -> {json.dumps([*args, PLAYWRIGHT_FLAG])}",
        "    PREREQUISITE: --extension needs the Playwright browser extension installed",
        "    in the Chrome/Edge profile you drive, or the server will fail to connect.",
    ]

    def mutate(cfg: dict[str, Any]) -> None:
        cfg["mcpServers"][PLAYWRIGHT_SERVER]["args"] = [
            *cfg["mcpServers"][PLAYWRIGHT_SERVER]["args"],
            PLAYWRIGHT_FLAG,
        ]

    return OpResult("playwright", Status.CHANGE, detail, mutate)


def build_plan(config: dict[str, Any], ops, repos) -> list[OpResult]:
    builders = {
        "serena-projects": lambda c: op_serena_projects(c, repos),
        "serena-root": op_serena_root,
        "grep": op_grep,
        "playwright": op_playwright,
    }
    return [builders[name](config) for name in ops]


def apply_plan(config: dict[str, Any], plan: list[OpResult]) -> dict[str, Any]:
    """Return a NEW config with every changing op applied. Never mutates ``config``."""
    updated = copy.deepcopy(config)
    for result in plan:
        if result.changes and result.mutate is not None:
            result.mutate(updated)
    return updated


# ------------------------------------------------------------------------- file i/o


def load_config(target: str) -> dict[str, Any]:
    with open(target, encoding="utf-8") as handle:
        return json.load(handle)


def dumps_config(config: dict[str, Any]) -> str:
    """Serialise in Claude Code's own style (indent=2, no trailing newline)."""
    return json.dumps(config, indent=2, ensure_ascii=False)


def write_config(target: str, config: dict[str, Any]) -> None:
    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(dumps_config(config))


def backup(target: str, stamp: str | None = None) -> str:
    stamp = stamp or time.strftime("%Y%m%d-%H%M%S")
    dest = f"{target}.bak-{stamp}"
    shutil.copy2(target, dest)
    return dest


def revert(target: str, backup_path: str) -> None:
    shutil.copy2(backup_path, target)


# ------------------------------------------------------------------------------ cli


def render_list(config: dict[str, Any], repos) -> list[str]:
    lines = ["LIVE STATE (read-only)", ""]
    root = config.get("disabledMcpServers") or []
    lines.append(f"  root disabledMcpServers : {len(root)} entries")
    lines.append(f"  root disables serena    : {SERENA in root}")
    servers = config.get("mcpServers") or {}
    lines.append(f"  mcpServers              : {len(servers)} registered")
    lines.append(f"  grep registered         : {GREP_SERVER in servers}")
    pw = servers.get(PLAYWRIGHT_SERVER)
    pw_args = pw.get("args") if isinstance(pw, dict) else None
    lines.append(f"  playwright args         : {json.dumps(pw_args)}")
    projects = config.get("projects") or {}
    disabling = [
        k
        for k, v in projects.items()
        if isinstance(v, dict) and SERENA in (v.get("disabledMcpServers") or [])
    ]
    lines.append(f"  project blocks          : {len(projects)}")
    lines.append(f"  ...disabling serena     : {len(disabling)}")
    lines.append("")
    lines.append("  scoped repo -> project keys:")
    for repo, keys in match_projects(config, repos).items():
        lines.append(f"    {repo}: {len(keys)}")
        for key in keys:
            lines.append(f"      {key}")
    misses = near_misses(config, repos)
    if misses:
        lines.append("")
        lines.append("  NEAR MISSES (contain a marker, not a whole segment; add with")
        lines.append("  --extra-project if you want them in scope):")
        for key in misses:
            lines.append(f"    {key}")
    return lines


def render_preflight(plan: list[OpResult]) -> list[str]:
    lines = ["PRE-FLIGHT", ""]
    for result in plan:
        lines.append(f"  [{result.status}] {result.name}")
        lines.extend(result.detail)
        lines.append("")
    changing = [r.name for r in plan if r.changes]
    lines.append(f"  ops that would change the file: {changing or 'NONE'}")
    return lines


def _guard(args: argparse.Namespace, out) -> int:
    """0 = safe to write. Non-zero = refuse (already reported)."""
    if args.ignore_claude_check:
        print(
            "WARNING: --ignore-claude-check set; skipping the live-session guard.",
            file=out,
        )
        print(
            "WARNING: a live session rewrites ~/.claude.json every ~30s and WILL",
            file=out,
        )
        print("WARNING: clobber this edit. You are on your own.", file=out)
        return 0
    try:
        alive = detect_claude()
    except Exception as exc:  # noqa: BLE001 - fail CLOSED on any probe failure
        print(f"REFUSING: cannot read the process table ({exc}).", file=out)
        print("REFUSING: failing closed - could not prove Claude is closed.", file=out)
        return 3
    if alive:
        print(f"REFUSING: Claude is RUNNING ({', '.join(alive)}).", file=out)
        print(
            "REFUSING: close every Claude session, then re-run with --apply.", file=out
        )
        print(
            "REFUSING: (--list and the dry-run preview work fine while it is open.)",
            file=out,
        )
        return 3
    return 0


def run(args: argparse.Namespace, out=None) -> int:
    # Resolved at CALL time: binding sys.stdout as a default would freeze the stream
    # captured at import, which silently swallows output under pytest capture.
    out = sys.stdout if out is None else out
    if args.revert_from:
        rc = _guard(args, out)
        if rc:
            return rc
        revert(args.target, args.revert_from)
        print(f"reverted {args.target} from {args.revert_from}", file=out)
        return 0

    config = load_config(args.target)
    repos = [*DEFAULT_SCOPED_REPOS, *args.extra_project]

    if args.list:
        print("\n".join(render_list(config, repos)), file=out)
        return 0

    plan = build_plan(config, args.only, repos)
    print("\n".join(render_preflight(plan)), file=out)

    if not any(r.changes for r in plan):
        print("\nnothing to do.", file=out)
        return 0
    if not args.apply:
        print("\n(dry-run - pass --apply to write)", file=out)
        return 0

    rc = _guard(args, out)
    if rc:
        return rc

    backup_path = backup(args.target)
    write_config(args.target, apply_plan(config, plan))
    print(f"\nbackup : {backup_path}", file=out)
    print(f"applied: {args.target}", file=out)
    print("Start Claude again for the change to take effect.", file=out)
    print(f"Undo with: --revert-from {backup_path}", file=out)
    return 0


def _csv_ops(raw: str) -> list[str]:
    picked = [p.strip() for p in raw.split(",") if p.strip()]
    bad = [p for p in picked if p not in OP_NAMES]
    if bad:
        raise argparse.ArgumentTypeError(
            f"unknown op(s) {bad}; choose from {list(OP_NAMES)}"
        )
    return picked


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reversible apply-when-closed batch for ~/.claude.json config flips."
    )
    parser.add_argument("--target", default=DEFAULT_TARGET, help="config file")
    parser.add_argument(
        "--only",
        type=_csv_ops,
        default=list(OP_NAMES),
        help=f"comma-separated subset of {list(OP_NAMES)} (default: all)",
    )
    parser.add_argument(
        "--extra-project",
        action="append",
        default=[],
        help="extra repo marker to scope serena-projects to (repeatable)",
    )
    parser.add_argument("--list", action="store_true", help="print live state and exit")
    parser.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    parser.add_argument("--revert-from", help="restore --target from this backup")
    parser.add_argument(
        "--ignore-claude-check",
        action="store_true",
        help="DANGEROUS: write even though a live session will clobber it",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    return run(parse_args(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    raise SystemExit(main())
