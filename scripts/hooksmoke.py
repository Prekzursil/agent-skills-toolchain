#!/usr/bin/env python3
"""hooksmoke.py - experiment E5: do hooks actually fire, in a real session, on this platform, in this tool?

Two independent measurements, both written to docs/results/E5-<tool>-<platform>-<timestamp>.json (never overwritten):

  1. MECHANISM  (--tool claude)   Registers one marker hook per event type (SessionStart, UserPromptSubmit,
                                  PreToolUse, PostToolUse, Stop) in a throwaway project, using the SAME
                                  invocation shape the live estate uses (`python "<absolute path>.py"`), starts
                                  a real non-interactive session, and reports which markers were written and
                                  what JSON each hook received on stdin. This is the class of failure the 2026
                                  Windows bug reports describe (hook composed for one shell, executed by another;
                                  silent deny; trust-hash after edit). A contract test cannot see it. This can.
                                  COVERAGE BOUNDARY: only the five events above are exercised -- they are the
                                  ones a single non-interactive echo turn can trigger. Other wired types
                                  (PreCompact, PostToolUseFailure, SessionEnd, Notification, Subagent*,
                                  PermissionRequest, WorktreeCreate) are listed in `events_not_covered` and
                                  reported UNTESTED, never as passing, so all_fired cannot be misread as full
                                  wired-event coverage.

  2. LIVE-DRY-RUN (--live <settings.json>)  Parses every hook command in the live settings file. By default
                                  (discovery only) it records only whether each command's interpreter resolves and
                                  each script path exists. With --execute it also invokes each command directly with
                                  a synthetic event on stdin, recording exit code, duration, stderr head -- catching
                                  dead paths, wrong interpreter, crashes on the current Python, and hooks that hang.

Usage (owner's Windows box, PowerShell):
    python hooksmoke.py --tool claude                                                # mechanism test: spawns one real, hook-isolated session
    python hooksmoke.py --live "$env:USERPROFILE\\.claude\\settings.json"            # discovery only (default): checks interpreters + script paths, runs nothing
    python hooksmoke.py --live "$env:USERPROFILE\\.claude\\settings.json" --execute  # STATEFUL: also runs each real hook once
Usage (Linux/macOS): same, with the appropriate settings path.

Codex and Cursor: the MECHANISM test needs their hook registration formats (Codex: .codex/hooks.json; Cursor:
hooks.json in the project). They are NOT implemented here on purpose rather than guessed; see TODO markers.
Selecting a not-yet-implemented tool exits non-zero (unsupported) unless --allow-skipped is passed, so scheduled
automation cannot bank a skipped tool as a passing E5 measurement.
The LIVE-DRY-RUN works for any tool's settings as long as the file has the Claude Code hooks shape.

WARNING: --live is discovery-only by default (per AGENTS.md: helper scripts default to read-only discovery). It
only checks that each command's interpreter resolves and each script path exists, running nothing. Add --execute
to actually invoke each real hook once with a synthetic event; hooks that notify, write ledgers or touch memory
will then do so. (--no-exec is the deprecated former name for the now-default discovery mode.)

Exit code: 0 if every registered marker fired and every live hook started and exited 0; non-zero otherwise
(1 = a marker missed or a hook failed; 2 = the selected mechanism tool is unimplemented and --allow-skipped
was not given).
Requires: Python 3.9+, the tool's CLI on PATH, valid credentials. One session costs a few cents.
"""

import argparse
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

EVENTS = ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"]

# The full catalog of Claude Code hook event types this instrument knows about. It is
# kept as a SUPERSET of everything wired in agent-self/config/settings.json (19 types as
# of this snapshot) plus the standard event types that snapshot does not wire (SessionEnd,
# Notification), so the derived "untested" set below can never silently omit a wired route.
# If a new event type is wired in a live config, add it here too; the live-dry-run path
# still reports it by reading that config directly.
KNOWN_EVENTS = [
    "SessionStart",
    "SessionEnd",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "PostToolUseFailure",
    "Stop",
    "StopFailure",
    "Notification",
    "PreCompact",
    "PostCompact",
    "PermissionRequest",
    "PermissionDenied",
    "SubagentStart",
    "SubagentStop",
    "ConfigChange",
    "TaskCreated",
    "TaskCompleted",
    "TeammateIdle",
    "WorktreeCreate",
    "WorktreeRemove",
]

# Hook event types this mechanism test does NOT register or trigger, derived from the
# catalog above rather than hand-maintained: everything known minus the five a single echo
# turn exercises. A non-interactive `claude -p` echo turn cannot deterministically produce
# a compaction, a failed tool call, a subagent, a permission prompt, a worktree op, a
# notification, a task/teammate event, or a clean session-end hook, so the instrument
# REPORTS every such type as untested instead of letting all_fired read as "every wired
# hook event fires". Deriving the list guarantees no wired-but-untested route is dropped.
UNCOVERED_EVENTS = [e for e in KNOWN_EVENTS if e not in EVENTS]

MARKER_SCRIPT = r"""
import json, os, sys, datetime
event = sys.argv[1]
outdir = sys.argv[2]
try:
    payload = sys.stdin.read()
except Exception as e:
    payload = "STDIN-ERROR: %r" % (e,)
rec = {"event": event, "utc": datetime.datetime.utcnow().isoformat(), "cwd": os.getcwd(),
       "python": sys.executable, "stdin_bytes": len(payload), "stdin_head": payload[:400]}
with open(os.path.join(outdir, event + ".marker.json"), "a", encoding="utf-8") as f:
    f.write(json.dumps(rec) + "\n")
print(json.dumps({"hooksmoke": event}))
"""


def utc_stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_result(results_dir: Path, tool: str, data: dict) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    base = results_dir / f"E5-{tool}-{platform.system().lower()}-{utc_stamp()}.json"
    payload = json.dumps(data, indent=2)
    out = base
    suffix = ord("a")
    # Exclusive creation ("x") reserves the name atomically, so two runs for the same tool
    # and platform in the same UTC second cannot both pick this filename and overwrite one
    # another -- an exists() check then write_text races and can silently discard a result.
    while True:
        try:
            with open(out, "x", encoding="utf-8") as fh:
                fh.write(payload)
            return out
        except FileExistsError:
            out = base.with_stem(f"{base.stem}-{chr(suffix)}")
            suffix += 1


# ---------------------------------------------------------------------------------------------
# 1. MECHANISM test
# ---------------------------------------------------------------------------------------------


def mechanism_claude(workdir: Path, marker_dir: Path, timeout: int) -> dict:
    """Register marker hooks in a throwaway project and run one real `claude -p` session."""
    marker_py = workdir / "hooksmoke_marker.py"
    marker_py.write_text(MARKER_SCRIPT, encoding="utf-8")
    # shlex.quote() wraps the path in POSIX single quotes, which cmd.exe and PowerShell take
    # literally -- so every marker hook would fail on Windows, this instrument's documented
    # target. Double quotes work in both shells (and match how marker_py/marker_dir are quoted
    # below); shlex.quote stays on POSIX for its stronger metacharacter handling.
    py = (
        f'"{sys.executable}"'
        if platform.system() == "Windows"
        else shlex.quote(sys.executable)
    )

    # Same shape as the live estate: python "<absolute path>" <args>
    def cmd(event):
        return f'{py} "{marker_py}" {event} "{marker_dir}"'

    hooks = {
        "SessionStart": [
            {"hooks": [{"type": "command", "command": cmd("SessionStart")}]}
        ],
        "UserPromptSubmit": [
            {"hooks": [{"type": "command", "command": cmd("UserPromptSubmit")}]}
        ],
        "PreToolUse": [
            {
                "matcher": "Bash",
                "hooks": [{"type": "command", "command": cmd("PreToolUse")}],
            }
        ],
        "PostToolUse": [
            {
                "matcher": "Bash",
                "hooks": [{"type": "command", "command": cmd("PostToolUse")}],
            }
        ],
        "Stop": [{"hooks": [{"type": "command", "command": cmd("Stop")}]}],
    }
    (workdir / ".claude").mkdir(exist_ok=True)
    (workdir / ".claude" / "settings.json").write_text(
        json.dumps({"hooks": hooks}, indent=2), encoding="utf-8"
    )
    # Isolate this session from the operator's user-scoped configuration. Changing only cwd
    # does NOT isolate it: Claude Code merges hooks from the real ~/.claude/settings.json with
    # the marker hooks in this throwaway project, so the mechanism test could silently run the
    # operator's stateful hooks (notifications, ledgers, memory writes) with no --live/--execute
    # and no warning. Point CLAUDE_CONFIG_DIR at a private dir carrying ONLY the credential
    # file, so auth survives but user hooks and settings do not. (macOS keychain auth is
    # unaffected by CLAUDE_CONFIG_DIR; the copied credential is scrubbed after the run.)
    iso_cfg = workdir / "isolated-config"
    iso_cfg.mkdir(exist_ok=True)
    src_cfg = Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude"))
    cred_names = (".credentials.json",)
    for cred in cred_names:
        s = src_cfg / cred
        if s.is_file():
            shutil.copy2(s, iso_cfg / cred)
    env = dict(os.environ)
    env["CLAUDE_CONFIG_DIR"] = str(iso_cfg)

    prompt = "Run exactly this shell command and then reply DONE: echo hooksmoke-bash"
    argv = [
        "claude",
        "-p",
        prompt,
        "--allowedTools",
        "Bash(echo*)",
        "--output-format",
        "json",
    ]
    t0 = time.time()
    try:
        proc = subprocess.run(
            argv,
            cwd=str(workdir),
            env=env,
            capture_output=True,
            text=True,
            errors="replace",  # never abort on non-UTF-8 bytes in the CLI's streams
            timeout=timeout,
        )
        rc, out, err = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        stdout_str = (
            (e.stdout or b"").decode("utf-8", errors="replace")
            if isinstance(e.stdout, bytes)
            else (e.stdout or "")
        )
        stderr_str = (
            (e.stderr or b"").decode("utf-8", errors="replace")
            if isinstance(e.stderr, bytes)
            else (e.stderr or "")
        )
        rc, out, err = (
            -1,
            stdout_str,
            f"TIMEOUT after {timeout}s: " + stderr_str,
        )
    except FileNotFoundError as e:
        rc, out, err = -2, "", f"claude CLI not found: {e}"
    except OSError as e:
        # e.g. the claude path exists but is not executable (PermissionError),
        # or any other OS-level spawn failure. Without this, rc/out/err would
        # be unbound and the return statement below would raise NameError.
        rc, out, err = -3, "", f"claude CLI could not be executed: {e}"
    dur = round(time.time() - t0, 1)
    # Do not leave a copy of the operator's credentials in the throwaway tree.
    for cred in cred_names:
        try:
            (iso_cfg / cred).unlink(missing_ok=True)
        except OSError:
            pass
    fired = {}
    for ev in EVENTS:
        f = marker_dir / f"{ev}.marker.json"
        if f.exists():
            lines = []
            for ln in f.read_text(encoding="utf-8").splitlines():
                if not ln.strip():
                    continue
                try:
                    lines.append(json.loads(ln))
                except json.JSONDecodeError:
                    # A subprocess killed mid-write (e.g. on timeout) can leave a
                    # partial, invalid JSON line; skip it rather than crash the
                    # whole report on one corrupted marker entry.
                    continue
            if lines:
                fired[ev] = {
                    "fired": True,
                    "count": len(lines),
                    "stdin_bytes": lines[0]["stdin_bytes"],
                    "stdin_head": lines[0]["stdin_head"][:200],
                }
            else:
                fired[ev] = {"fired": False, "reason": "marker file empty"}
        else:
            fired[ev] = {"fired": False}
    return {
        "tool": "claude",
        "argv": argv,
        "rc": rc,
        "duration_s": dur,
        "stdout_tail": out[-800:],
        "stderr_tail": err[-800:],
        "settings_used": str(workdir / ".claude" / "settings.json"),
        "config_dir_isolated": str(iso_cfg),
        "events": fired,
        "all_fired": all(v["fired"] for v in fired.values()),
        "events_not_covered": UNCOVERED_EVENTS,
        "coverage_note": (
            f"all_fired covers only the {len(EVENTS)} events a single echo session can "
            f"trigger; the other {len(UNCOVERED_EVENTS)} of {len(KNOWN_EVENTS)} known hook "
            "event types (a superset of everything the live settings wire) are untested "
            "here, not confirmed working"
        ),
    }


def mechanism_codex(workdir: Path, marker_dir: Path, timeout: int) -> dict:
    # TODO(owner): Codex CLI hooks live in .codex/hooks.json; confirm the current schema in the Codex docs
    # (developers.openai.com/codex) before enabling. Codex also hashes hook commands for trust: a hook edited
    # after first trust silently stops until re-trusted, which is itself a thing this test should detect.
    return {
        "tool": "codex",
        "skipped": True,
        "reason": "hook registration format not implemented here on purpose; see TODO",
    }


def mechanism_cursor(workdir: Path, marker_dir: Path, timeout: int) -> dict:
    # TODO(owner): cursor-agent imports Claude Code hooks (no opt-out as of 2026-09) and has been reported to
    # compose them as PowerShell but execute with bash on Windows, silently denying every tool call. The most
    # informative Cursor test is therefore: run `cursor-agent -p` in the SAME throwaway project used for the
    # claude mechanism test and see whether the markers fire or the session hard-denies. Not automated here.
    return {
        "tool": "cursor",
        "skipped": True,
        "reason": "not automated; run cursor-agent in the throwaway project by hand",
    }


# ---------------------------------------------------------------------------------------------
# 2. LIVE-DRY-RUN
# ---------------------------------------------------------------------------------------------


def synthetic_event(event: str, cwd: str) -> str:
    base = {
        "session_id": "hooksmoke",
        "transcript_path": os.path.join(cwd, "hooksmoke-transcript.jsonl"),
        "cwd": cwd,
        "hook_event_name": event,
    }
    if event == "PreToolUse" or event == "PostToolUse":
        base.update({"tool_name": "Bash", "tool_input": {"command": "echo hooksmoke"}})
        if event == "PostToolUse":
            base["tool_response"] = {
                "stdout": "hooksmoke\n",
                "stderr": "",
                "interrupted": False,
            }
    if event == "UserPromptSubmit":
        base["prompt"] = "hooksmoke"
    if event == "Stop":
        base["stop_hook_active"] = False
    return json.dumps(base)


def iter_hook_commands(settings: dict):
    for event, groups in (settings.get("hooks") or {}).items():
        for g in groups or []:
            for h in g.get("hooks") or []:
                if h.get("type") == "command" and h.get("command"):
                    yield (
                        event,
                        g.get("matcher", ""),
                        h["command"],
                        int(h.get("timeout", 60) or 60),
                    )


def live_dry_run(
    settings_path: Path, per_hook_timeout: int, execute: bool = True
) -> dict:
    try:
        settings = json.loads(Path(settings_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        # A missing, unreadable, or malformed settings file must be recorded as a failed
        # live check, not raised: a combined mechanism/live invocation would otherwise
        # discard the mechanism measurement already collected and write no result artifact.
        return {
            "settings": str(settings_path),
            "executed": execute,
            "error": f"could not load settings: {type(e).__name__}: {e}",
            "hooks_total": 0,
            "hooks_exit0": 0,
            "hooks_failed": [],
            "rows": [],
        }
    rows = []
    cwd = str(Path.cwd())
    for event, matcher, command, declared_timeout in iter_hook_commands(settings):
        # Interpreter and path checks (best effort, string-based; the real test is the run below)
        # shlex.split(posix=False) keeps a quoted interpreter path with spaces (e.g. Windows
        # "C:\Program Files\Python\python.exe") as one token and preserves backslashes; a naive
        # .split() would break it at the space and report a valid interpreter as missing. Fall
        # back to a naive split only if the command has unbalanced quotes (shlex raises).
        stripped = command.strip()
        try:
            parts = shlex.split(stripped, posix=False)
        except ValueError:
            parts = stripped.split()
        first = parts[0].strip("\"'") if parts else ""
        interp_ok = shutil.which(first) is not None or Path(first).exists()
        # Detect script arguments from the tokenized command so single-quoted ('...'),
        # double-quoted ("...") and bare paths are all recognized; command.split('"')
        # alone missed a valid POSIX hook like `python '/missing/hook.py'` and let it
        # pass discovery with path_ok=None even though the script is absent.
        scripts = [
            t.strip("\"'") for t in parts if t.strip("\"'").endswith((".py", ".ps1"))
        ]
        path_ok = all(Path(p).exists() for p in scripts) if scripts else None
        if not execute:
            rc = 0 if (interp_ok and path_ok is not False) else 3
            rows.append(
                {
                    "event": event,
                    "matcher": matcher,
                    "command": command,
                    "interpreter_resolves": interp_ok,
                    "script_paths_exist": path_ok,
                    "rc": rc,
                    "duration_s": 0.0,
                    "stdout_head": "",
                    "stderr_head": ""
                    if rc == 0
                    else "NO-EXEC: interpreter or script path missing",
                }
            )
            continue
        t0 = time.time()
        try:
            proc = subprocess.run(
                command,
                shell=True,
                input=synthetic_event(event, cwd),
                capture_output=True,
                text=True,
                errors="replace",  # a hook emitting non-UTF-8 bytes must be recorded,
                # not abort the whole --live run with UnicodeDecodeError while decoding streams
                timeout=min(per_hook_timeout, declared_timeout),
            )
            rc, err, out = proc.returncode, proc.stderr, proc.stdout
        except subprocess.TimeoutExpired as e:
            stdout_str = (
                (e.stdout or b"").decode("utf-8", errors="replace")
                if isinstance(e.stdout, bytes)
                else (e.stdout or "")
            )
            stderr_str = (
                (e.stderr or b"").decode("utf-8", errors="replace")
                if isinstance(e.stderr, bytes)
                else (e.stderr or "")
            )
            rc, err, out = -1, "TIMEOUT " + stderr_str, stdout_str
        except (OSError, ValueError) as e:
            # Running arbitrary hook commands can raise OSError (e.g. a
            # non-executable interpreter) or ValueError (a malformed argv);
            # without this rc/err/out would be unbound and the row append below
            # would raise NameError, aborting the whole dry run.
            rc, err, out = -3, f"hook could not be executed: {e}", ""
        rows.append(
            {
                "event": event,
                "matcher": matcher,
                "command": command,
                "interpreter_resolves": interp_ok,
                "script_paths_exist": path_ok,
                "rc": rc,
                "duration_s": round(time.time() - t0, 2),
                "stdout_head": out[:200],
                "stderr_head": err[:300],
            }
        )
    ok = [r for r in rows if r["rc"] == 0]
    return {
        "settings": str(settings_path),
        "executed": execute,
        "hooks_total": len(rows),
        "hooks_exit0": len(ok),
        "hooks_failed": [r for r in rows if r["rc"] != 0],
        "rows": rows,
    }


# ---------------------------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--tool",
        choices=["claude", "codex", "cursor"],
        help="run the MECHANISM test for this tool",
    )
    ap.add_argument(
        "--live", type=Path, help="path to the live settings.json for the LIVE-DRY-RUN"
    )
    ap.add_argument(
        "--results",
        type=Path,
        default=Path("docs/results"),
        help="results directory (default docs/results, the committed E5 archive the "
        "protocol and runbook reference)",
    )
    ap.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="session timeout seconds for the mechanism test",
    )
    ap.add_argument(
        "--hook-timeout",
        type=int,
        default=30,
        help="per-hook timeout seconds for the live dry run",
    )
    ap.add_argument(
        "--execute",
        action="store_true",
        help="with --live: actually RUN each configured hook once. This is STATEFUL -- the "
        "hooks can notify, write ledgers, or mutate memory -- so it is off by default and "
        "must be requested explicitly.",
    )
    ap.add_argument(
        "--allow-skipped",
        action="store_true",
        help="exit 0 even when the selected mechanism tool is unimplemented (skipped). Off by "
        "default so scheduled automation cannot bank a skipped tool as a passing E5 measurement.",
    )
    ap.add_argument(
        "--no-exec",
        action="store_true",
        help="deprecated: dry-run (check interpreters and script paths, run nothing) is now "
        "the default. Kept as an explicit no-op; if given with --execute it wins, so nothing "
        "runs.",
    )
    args = ap.parse_args()
    if not args.tool and not args.live:
        ap.error("give --tool and/or --live")

    report = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python": sys.executable,
        "cwd": str(Path.cwd()),
    }
    exit_code = 0

    if args.tool:
        workdir = Path(tempfile.mkdtemp(prefix="hooksmoke-"))
        marker_dir = workdir / "markers"
        marker_dir.mkdir()
        fn = {
            "claude": mechanism_claude,
            "codex": mechanism_codex,
            "cursor": mechanism_cursor,
        }[args.tool]
        report["mechanism"] = fn(workdir, marker_dir, args.timeout)
        report["mechanism"]["workdir"] = str(workdir)
        m = report["mechanism"]
        if m.get("skipped"):
            # A skipped mechanism (an unimplemented tool) measured nothing; treat it as
            # unsupported (exit 2) rather than success so scheduled automation cannot bank
            # it as a passing E5 run. --allow-skipped opts back into exit 0 for interactive use.
            if not args.allow_skipped:
                exit_code = 2
        elif not m.get("all_fired") or m.get("rc") != 0:
            # A session that fired every marker hook but exited nonzero (e.g. its final
            # response or API operation failed after Stop ran) is a failed measurement, not
            # a clean E5 pass -- gate on rc as well as all_fired so automation cannot accept
            # it as success.
            exit_code = 1

    if args.live:
        report["live_dry_run"] = live_dry_run(
            args.live, args.hook_timeout, execute=args.execute and not args.no_exec
        )
        lv = report["live_dry_run"]
        if lv.get("error") or lv["hooks_failed"]:
            exit_code = 1

    out = write_result(args.results, args.tool or "live", report)
    # Human summary
    if "mechanism" in report:
        m = report["mechanism"]
        if m.get("skipped"):
            print(f"[mechanism:{m['tool']}] skipped: {m['reason']}")
        else:
            print(
                f"[mechanism:{m['tool']}] rc={m['rc']} duration={m['duration_s']}s all_fired={m['all_fired']}"
            )
            for ev, v in m["events"].items():
                print(
                    f"   {ev:18s} fired={v['fired']}"
                    + (f" stdin_bytes={v['stdin_bytes']}" if v["fired"] else "")
                )
            uncovered = m.get("events_not_covered") or []
            if uncovered:
                print(f"   untested (not triggerable here): {', '.join(uncovered)}")
    if "live_dry_run" in report:
        live = report["live_dry_run"]
        if live.get("error"):
            print(f"[live-dry-run] FAILED: {live['error']}")
        mode = (
            "started and exited 0"
            if live["executed"]
            else "have a resolvable interpreter and existing script path (not executed)"
        )
        print(
            f"[live-dry-run] {live['hooks_exit0']}/{live['hooks_total']} hooks {mode}"
        )
        for r in live["hooks_failed"]:
            print(
                f"   FAIL rc={r['rc']} {r['event']}: {r['command'][:90]} :: {r['stderr_head'][:120]!r}"
            )
    print(f"result written: {out}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
