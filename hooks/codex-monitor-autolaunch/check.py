#!/usr/bin/env python3
r"""codex-monitor-autolaunch/check.py — PreToolUse hook (CLI-launch complement).

Opens the out-of-repo **mingle codex-monitor** dashboard when Claude starts Codex work from the
COMMAND LINE — a `codex exec` / `codex mcp` command run through Bash or PowerShell. The native
`mcp__codex__codex` MCP tool is owned by the registry-driven `monitor-autolaunch` hook (→ `mon
codexmon`), so this hook deliberately does NOT fire on it: keeping the two paths disjoint avoids a
double launch (the codexmon board AND this dashboard) on a single Codex call. A `monitors.toml`
`trigger_tool` is a single tool name and cannot express "a codex CLI command inside a
Bash/PowerShell call", so this hook stays as the CLI-launch complement. It opens ONCE per session
(a per-session lockfile, so it never spams windows) in its own `codexmon-cli` window — distinct
from codexmon's window so the two boards never dock into each other — and injects a one-line
reminder.

READ-ONLY monitor (it never launches/steers/kills Codex). FAIL-OPEN (any error -> exit 0, no
output, never blocks the tool). Opt-out: `CODEX_MONITOR_AUTOLAUNCH=off` in env, or a `.disabled`
file beside this script.

Wire via the _dispatch manifest (PreToolUse, matcher `Bash|PowerShell`); the dispatcher fires on
Bash/PowerShell tools and this hook self-filters to `codex exec` / `codex mcp` command text.

TRANSPORT-CONTRACT PREFLIGHT (added for D-a004)
-----------------------------------------------
This hook was the ONLY check `_dispatch/manifest.json` selected for a Bash/PowerShell
`codex exec` (manifest.json:248-255), and it did nothing but open a dashboard -- so a
noncanonical dispatch entered the tool path with none of the guarantees
`rules/common/cross-vendor-dispatch.md` requires (no background dispatch :7-17; AND-gated
result, prompt-by-file, `--ignore-user-config`, terminal state, explicit 30-min timeout
:19-30/:32-46/:55-66) and `agents/codex.md:28-36,50,101` implements. `transport_violations()`
now preflights that command and injects a redirect to the canonical adapter.

It ADVISES, never blocks: `dispatch.py` is inject-only (dispatch.py:44-45) and an exit-2 gate
folded into it is *silently disarmed* (`_dispatch/test_manifest_presence.py:51-53`), so a hard
block here would be worse than useless -- it would look enforced and not be.

The two opt-outs are deliberately INDEPENDENT: `CODEX_MONITOR_AUTOLAUNCH=off` suppresses the
dashboard only (D-a004 measured that flag reducing this hook to `aggregate=None`), while
`CODEX_TRANSPORT_PREFLIGHT=off` suppresses the advisory only. A `.disabled` file still turns
the whole hook off.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

THIS = Path(__file__).resolve().parent
DISABLED = THIS / ".disabled"
# Repointed 2026-07-18: was ~/.local/opt/mingle/monitor/launch.ps1 (the RETIRED legacy
# monitor — it accumulated one orphan per session across ~27 sessions AND cleared the main
# terminal buffer, destroying scrollback). Now the guarded monitorcore wrapper: its
# machine-wide single-instance guard caps the fleet at ONE board total, and it launches
# monitorcore (the merged PR-B3 board), not the legacy fork. MASTER-QUEUE T0-2.
LAUNCH = Path(os.path.expanduser("~")) / ".local" / "bin" / "codexmon.ps1"
_DETACHED = 0x00000008  # DETACHED_PROCESS — don't tie the launched window to the hook


def _is_codex_launch(payload: dict) -> bool:
    """True iff this is a CLI Codex launch — ``codex exec`` / ``codex mcp`` via Bash/PowerShell.

    The native ``mcp__codex__codex`` tool is intentionally NOT matched here (the registry-driven
    ``monitor-autolaunch`` hook owns that path → ``mon codexmon``), so the two never double-fire.
    """
    tn = str((payload or {}).get("tool_name") or "")
    if tn in ("Bash", "PowerShell"):
        cmd = str(((payload or {}).get("tool_input") or {}).get("command") or "")
        if "codex exec" in cmd or "codex mcp" in cmd:
            return True
    return False


# --- transport-contract preflight (D-a004) -------------------------------------------
# A work-unit dispatch is `codex exec`. `codex mcp` starts the MCP server and `codex exec
# resume` is the adapter's own documented repair step (agents/codex.md:76) -- neither is a
# fresh work-unit dispatch, so neither is preflighted.
_EXEC = re.compile(r"\bcodex\s+exec\b")
_RESUME = re.compile(r"\bcodex\s+exec\s+resume\b")

# Backgrounding, in every form the rule bans (cross-vendor-dispatch.md:7-17;
# agents/codex.md:101). A backgrounded job's result is unreachable in practice.
_BACKGROUND = (
    (re.compile(r"--background\b"), "--background"),
    (re.compile(r"\bnohup\b"), "nohup"),
    (re.compile(r"(?<![&>])&\s*$"), "a trailing `&`"),
    (re.compile(r"\bStart-Process\b", re.I), "Start-Process"),
    (re.compile(r"\bstart\s+/b\b", re.I), "start /b"),
)

# Prompt staged off the command line: a `<` redirect, an explicit --prompt-file, or a pipe
# into codex. Windows caps the command line at 32,767 chars (agents/codex.md:20-22).
_STAGED_PROMPT = (
    re.compile(r"<\s*\S"),
    re.compile(r"--prompt-file\b"),
    re.compile(r"\|\s*codex\s+exec\b"),
)

# The only result channel the adapter trusts (agents/codex.md:70-71).
_RESULT_CHANNEL = re.compile(r"(?:^|\s)-o(?:\s|=)|--output-last-message\b")

_MIN_TIMEOUT_MS = 1800000  # 30 min (agents/codex.md:50)


def transport_violations(payload: dict) -> list[str]:
    """Return the cross-vendor transport-contract violations in a Codex CLI dispatch.

    Empty list == compliant, not-a-dispatch, or undecidable. Pure: no I/O, no side
    effects, so it is safe to call from anywhere and trivial to test.
    """
    payload = payload or {}
    if str(payload.get("tool_name") or "") not in ("Bash", "PowerShell"):
        return []
    tool_input = payload.get("tool_input") or {}
    cmd = str(tool_input.get("command") or "")
    if not _EXEC.search(cmd) or _RESUME.search(cmd):
        return []

    out: list[str] = []
    for pattern, label in _BACKGROUND:
        if pattern.search(cmd):
            out.append(f"backgrounded via `{label}` -- the result is unreachable")
            break
    if tool_input.get("run_in_background"):
        out.append("backgrounded via the tool's own `run_in_background` param")
    if not any(p.search(cmd) for p in _STAGED_PROMPT):
        out.append(
            "the prompt is inlined, not staged on disk -- Windows caps the command "
            "line at 32,767 chars; write it to a file and pass it on stdin"
        )
    if "--ignore-user-config" not in cmd:
        out.append(
            "missing `--ignore-user-config` -- the active MCP inventory blows the arg "
            "cap and voids --output-schema"
        )
    if not _RESULT_CHANNEL.search(cmd):
        out.append(
            "no `-o`/`--output-last-message` result channel -- exit 0 alone is "
            "`severed-stream`, not SUCCESS"
        )
    timeout = tool_input.get("timeout")
    if not isinstance(timeout, (int, float)) or timeout < _MIN_TIMEOUT_MS:
        out.append(
            f"no explicit {_MIN_TIMEOUT_MS} ms timeout -- the silent 10-min default is "
            "what a prior run rationalised `--background` to escape"
        )
    return out


def _preflight(payload: dict) -> None:
    """Inject a redirect to the canonical adapter for a noncanonical dispatch."""
    if os.environ.get("CODEX_TRANSPORT_PREFLIGHT", "").lower() == "off":
        return
    violations = transport_violations(payload)
    if not violations:
        return
    _emit(
        "Cross-vendor transport contract violation "
        "(rules/common/cross-vendor-dispatch.md): "
        + "; ".join(violations)
        + ". Dispatch work units through the canonical adapter instead — "
        "agents/codex.md:28-36. Advisory only; `CODEX_TRANSPORT_PREFLIGHT=off` silences."
    )


def _launch() -> bool:
    """Open codex-monitor in a reusable named Windows-Terminal window; fall back to a console."""
    for cmd in (
        [
            "wt",
            "-w",
            "codexmon-cli",
            "new-tab",
            "--title",
            "codexmon-cli",
            "powershell",
            "-NoProfile",
            "-File",
            str(LAUNCH),
        ],
        [
            "cmd",
            "/c",
            "start",
            "codexmon-cli",
            "powershell",
            "-NoProfile",
            "-File",
            str(LAUNCH),
        ],
    ):
        try:
            subprocess.Popen(cmd, creationflags=_DETACHED, close_fds=True)
            return True
        except Exception:  # noqa: BLE001 — try the next launcher
            continue
    return False


def _emit(msg: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": msg,
                }
            }
        )
    )


def main() -> None:
    try:
        if DISABLED.exists():
            return
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:  # noqa: BLE001 — fail-open
        return
    # The contract preflight runs BEFORE, and independently of, the dashboard. Gating it
    # on CODEX_MONITOR_AUTOLAUNCH would let a monitoring opt-out silently re-open D-a004.
    try:
        _preflight(payload)
    except Exception:  # noqa: BLE001 — fail-open
        pass
    try:
        if os.environ.get("CODEX_MONITOR_AUTOLAUNCH", "").lower() == "off":
            return
        if not _is_codex_launch(payload):
            return
        if not LAUNCH.exists():
            return
        sid = "".join(
            c for c in str((payload or {}).get("session_id") or "x") if c.isalnum()
        )[:16]
        lock = Path(tempfile.gettempdir()) / f"codexmon-autolaunch-{sid}.lock"
        if lock.exists():
            _emit(
                "🛰 codex-monitor is watching your Codex threads live (already opened this session · `/codex-monitor` to reopen)."
            )
            return
        launched = _launch()
        try:
            lock.write_text("1", encoding="utf-8")
        except OSError:
            pass
        if launched:
            _emit(
                "🛰 Opened **codex-monitor** (read-only Codex thread dashboard) in a 'codexmon-cli' window — watch your Codex threads' prompt/tools/tokens/status live. `/codex-monitor` reopens it; `CODEX_MONITOR_AUTOLAUNCH=off` disables."
            )
        else:
            _emit(
                "🛰 Tip: run `/codex-monitor` to watch your Codex threads live (thread prompt/tools/tokens/status)."
            )
    except Exception:  # noqa: BLE001 — fail-open
        return


if __name__ == "__main__":
    main()
