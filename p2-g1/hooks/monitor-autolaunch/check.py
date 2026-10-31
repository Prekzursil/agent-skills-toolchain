#!/usr/bin/env python3
r"""monitor-autolaunch/check.py — generalized PreToolUse monitor auto-launcher (matcher: Task|Workflow|mcp__codex__codex).

The generalized successor to the wfmon-only workflow-monitor-autolaunch hook. Reads the
``monitors.toml`` registry through the shared, 100%-gated ``monitorcore.monitors`` core; for every
registered monitor whose ``trigger_tool`` matches the tool Claude is about to run
(``Workflow`` → wfmon, ``Task`` → agentmon, ``mcp__codex__codex`` → codexmon, …) it acts per the
monitor's ``autolaunch`` mode:
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

The manifest and the repo's settings.json projection route Workflow through the dispatcher and
have dropped the legacy standalone Workflow entry. That wiring is now DEPLOYED too: measured
2026-08-17 the live ``~/.claude/settings.json`` still omitted Workflow from the dispatcher matcher
and retained the legacy entry, so this hook was unreachable on that rail; on 2026-08-18
``agent-self/deploy_dispatch_wiring.py --apply`` carried both halves across in one atomic write,
and a Workflow tool call now reaches this hook through the dispatcher with the legacy group gone.

The superseded-lock alias below still matters and is kept: it shares a lock NAMESPACE with the
legacy hook, and _claim_session claims it ATOMICALLY before launching, so re-wiring that hook (or
restoring a settings backup taken before the deploy) cannot produce two tabs. The alias alone was
never sufficient -- exists()-then-write left a window in which two concurrent fires both saw no
lock and both opened a tab. That is not a thought experiment: measured 2026-08-18 against the
file this one replaced, 8 concurrent Workflow fires in ONE session opened 2, 2 and 3 times across
three runs, while this version opened exactly once in all three (test_07 reproduces it in-suite).
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

#: Monitors whose superseded per-monitor hook may still be wired in settings.json and contests
#: the SAME trigger with an IDENTICAL launch argv. Honouring that hook's lock name as an alias
#: makes migration order-independent: whichever hook fires first claims BOTH names, so the other
#: stands down instead of opening a second tab of the same board in the same window. Only wfmon
#: qualifies -- codex-monitor-autolaunch already self-narrows (check.py:63-74,
#: ``mcp__codex__codex`` deliberately unmatched) and opens a DIFFERENT board (``codexmon-cli`` /
#: codexmon.ps1), so aliasing it would suppress a distinct window.
_SUPERSEDED_LOCK_STEMS = {"wfmon": "wfmon-autolaunch"}


def _session_locks(name: str, sid: str) -> list[Path]:
    tmp = Path(tempfile.gettempdir())
    locks = [tmp / f"monitor-autolaunch-{name}-{sid}.lock"]
    stem = _SUPERSEDED_LOCK_STEMS.get(name)
    if stem:
        locks.append(tmp / f"{stem}-{sid}.lock")
    return locks


def _claim_session(lock: Path) -> bool | None:
    """Atomically claim ``lock``; None means dedup is unavailable and execution may proceed."""
    try:
        with lock.open("x", encoding="utf-8") as handle:
            handle.write("1")
        return True
    except FileExistsError:
        return False
    except OSError:
        # Fail open: lock failures must not block the tool or suppress the requested monitor.
        return None


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
            locks = _session_locks(spec.name, sid)
            # The alias is the legacy hook's contended name. Claim exactly one deterministic
            # lock so competing processes cannot each claim a different name and both stand down.
            claim_lock = locks[-1]
            # One-shot snapshot monitors (autolaunch="remind", e.g. agentmon) must NOT be
            # auto-opened: at a Task's PreToolUse the just-triggered agent's transcript does not
            # exist yet, so the spawner would flash an empty window and the per-session lock would
            # then never retry. Nudge the user to open it by hand once the agents are live. Read
            # the field defensively — a stale deployed spec without it falls back to "open".
            # Today remind-mode monitors have no alias, but handled-session semantics stay uniform.
            if getattr(spec, "autolaunch", "open") == "remind":
                if not any(lock.exists() for lock in locks):
                    claimed = _claim_session(claim_lock)
                    if claimed is False:
                        continue
                    _emit(
                        f"🛰 This {tool} will spawn agents — run `mon {spec.name}` to live-tail "
                        f"them once they're running (one tail window per active agent)."
                    )
                    for lock in locks:
                        if claimed and lock == claim_lock:
                            continue
                        try:
                            lock.write_text("1", encoding="utf-8")
                        except OSError:
                            pass
                continue
            if any(lock.exists() for lock in locks):
                _emit(
                    f"🛰 {spec.name} is watching this {tool} live "
                    f"(already opened this session · `mon {spec.name}` to reopen)."
                )
                continue
            claimed = _claim_session(claim_lock)
            if claimed is False:
                _emit(
                    f"🛰 {spec.name} is watching this {tool} live "
                    f"(already opened this session · `mon {spec.name}` to reopen)."
                )
                continue
            launched = _launch(mc, spec.name, entry)
            for lock in locks:
                if claimed and lock == claim_lock:
                    continue
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
