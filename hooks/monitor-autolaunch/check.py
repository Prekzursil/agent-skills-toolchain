#!/usr/bin/env python3
r"""monitor-autolaunch/check.py — generalized PreToolUse monitor auto-launcher (matcher: Task|Workflow).

The generalized successor to the wfmon-only workflow-monitor-autolaunch hook. Reads the
``monitors.toml`` registry through the shared, 100%-gated ``monitorcore.monitors`` core; for every
registered monitor whose ``trigger_tool`` matches the tool Claude is about to run
(``Workflow`` → wfmon, ``Task`` → agentmon, …) it acts per the monitor's ``autolaunch`` mode:
``"open"`` opens that monitor ONCE per session in a reusable named Windows-Terminal window (via
the shared launch-argv builder) — correct for a persistent poller like wfmon; ``"remind"`` skips
the launch and emits a one-time ``mon <name>`` nudge instead — correct for a one-shot spawner like
agentmon that would otherwise race the not-yet-created transcript at PreToolUse. The reminder is
folded into ``_emit`` and iterated PER matched monitor — there is no separate reminder hook.

THIN SHIM: all parsing / trigger-matching / argv-building lives in ``monitorcore.monitors``; this
file owns only the per-session lock, the opt-out gates, the DETACHED spawn, and the reminder text.

READ-ONLY monitor (never touches the run). FAIL-OPEN (any error → exit 0, no output, never blocks
the tool). Opt-out: global ``MONITOR_AUTOLAUNCH=off`` (env) or a ``.disabled`` file beside this
script; per-monitor ``MONITOR_AUTOLAUNCH_<NAME>=off``.

Wired via the _dispatch manifest (PreToolUse, matcher ``Task|Workflow``); the outer settings
matcher already passes both Task and Workflow, so the dispatcher fires for either trigger.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

THIS = Path(__file__).resolve().parent
DISABLED = THIS / ".disabled"
_GLOBAL_OFF = "MONITOR_AUTOLAUNCH"
_DETACHED = 0x00000008  # DETACHED_PROCESS — don't tie the launched window to the hook


def _monitorcore():
    """Import the vendored ``monitorcore.monitors`` (from the workflow-monitor skill)."""
    root = Path(os.path.expanduser("~")) / ".agents" / "skills" / "workflow-monitor"
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from monitorcore import monitors  # noqa: PLC0415 — deferred until the skill is on sys.path

    return monitors


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


def _opted_out(name: str) -> bool:
    """Global or per-monitor (``MONITOR_AUTOLAUNCH_<NAME>=off``) opt-out."""
    if os.environ.get(_GLOBAL_OFF, "").lower() == "off":
        return True
    return os.environ.get(f"{_GLOBAL_OFF}_{name.upper()}", "").lower() == "off"


def _launch(mc, name: str, entry: str) -> bool:
    """Open ``entry`` DETACHED via the shared launch ladder; True on the first rung that starts."""
    for argv in mc.launch_argvs(name, entry):
        try:
            subprocess.Popen(argv, creationflags=_DETACHED, close_fds=True)
            return True
        except Exception:  # noqa: BLE001 — try the next rung
            continue
    return False


def main() -> None:
    try:
        if DISABLED.exists() or os.environ.get(_GLOBAL_OFF, "").lower() == "off":
            return
        payload = json.loads(sys.stdin.read() or "{}")
        tool = str((payload or {}).get("tool_name") or "")
        if not tool:
            return
        mc = _monitorcore()
        specs = mc.load_monitors(mc.default_monitors_path())
        matched = mc.match_triggers(specs, tool)
        if not matched:
            return
        sid = "".join(
            c for c in str((payload or {}).get("session_id") or "x") if c.isalnum()
        )[:16]
        skills_root = mc.default_skills_root()
        for spec in matched:
            if _opted_out(spec.name):
                continue
            entry = mc.resolve_entry(spec, skills_root)
            if not Path(entry).exists():
                continue
            lock = (
                Path(tempfile.gettempdir())
                / f"monitor-autolaunch-{spec.name}-{sid}.lock"
            )
            # One-shot snapshot monitors (autolaunch="remind", e.g. agentmon) must NOT be
            # auto-opened: at a Task's PreToolUse the just-triggered agent's transcript does not
            # exist yet, so the spawner would flash an empty window and the per-session lock would
            # then never retry. Nudge the user to open it by hand once the agents are live. Read
            # the field defensively — a stale deployed spec without it falls back to "open".
            if getattr(spec, "autolaunch", "open") == "remind":
                if not lock.exists():
                    _emit(
                        f"🛰 This {tool} will spawn agents — run `mon {spec.name}` to live-tail "
                        f"them once they're running (one tail window per active agent)."
                    )
                    try:
                        lock.write_text("1", encoding="utf-8")
                    except OSError:
                        pass
                continue
            if lock.exists():
                _emit(
                    f"🛰 {spec.name} is watching this {tool} live "
                    f"(already opened this session · `mon {spec.name}` to reopen)."
                )
                continue
            launched = _launch(mc, spec.name, entry)
            try:
                lock.write_text("1", encoding="utf-8")
            except OSError:
                pass
            if launched:
                _emit(
                    f"🛰 Opened the **{spec.name}** monitor in a '{spec.name}' window/tab — "
                    f"watch this {tool}'s agents live. `mon {spec.name}` reopens it; "
                    f"`{_GLOBAL_OFF}=off` disables all, `{_GLOBAL_OFF}_{spec.name.upper()}=off` just this one."
                )
            else:
                _emit(
                    f"🛰 Tip: run `mon {spec.name}` to watch this {tool}'s agents live."
                )
    except Exception:  # noqa: BLE001 — fail-open
        return


if __name__ == "__main__":
    main()
