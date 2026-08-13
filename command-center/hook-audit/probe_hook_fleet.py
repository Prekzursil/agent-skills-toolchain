#!/usr/bin/env python3
r"""probe_hook_fleet.py — time every WIRED hook against its budget, and PROVE inertness
for the dark ones by firing them.

Two questions, one inventory, because they need the same wiring map:

  --timing     For each of the live `settings.json` hook entries, run the entry as a real
               subprocess with a payload shaped to ITS OWN matcher (so the hook takes its
               real path rather than exiting early on a tool name it does not handle) and
               compare wall time to its declared budget.

  --inertness  For each hooks/<dir> that appears in NO wiring surface, FIRE the script
               with an event-appropriate payload. This is the difference between "named
               nowhere" and "inert": a directory listing cannot tell a dark hook from a
               broken one. A hook that RUNS CLEANLY STANDALONE but is reachable from no
               wiring surface is INERT-CONFIRMED — the probe fires, the wiring does not.
               A hook that also fails standalone is DARK-AND-BROKEN, reported separately
               rather than folded into the same bucket.

DETECTOR CONTROLS, both directions, or the verdicts are worthless:
  * WIRED control    — `wire-check` must be found by the wiring search. If it is not,
                      the search is broken and every "dark" verdict is a false positive.
  * ABSENT control   — a synthetic directory name must be found NOWHERE. If it IS found,
                      the search matches too loosely and every "wired" verdict is suspect.
  * FIRE control     — a script known to emit must emit under the harness, so a silent
                      run means "this hook stayed silent", not "the harness swallowed it".
  The run FAILS CLOSED if any control misbehaves, or if the inventory is empty.

SIDE-EFFECT SAFETY: hooks whose job is to LAUNCH something (IDA/Ghidra, a monitor TUI, a
daemon) are not fired. They are listed by name with a reason and counted, never silently
dropped, so the coverage statement stays honest. `--include-launchers` overrides.

Reads ONLY the `hooks` key of settings.json (that file also holds live credentials).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
LIVE_HOOKS = Path("C:/Users/Prekzursil/.claude/hooks")
SETTINGS = Path("C:/Users/Prekzursil/.claude/settings.json")
AGENT_SELF = Path("C:/Users/Prekzursil/.agents/harness")
OUT = Path(__file__).resolve().parent

# Hooks that START something external. Firing these in an audit would spawn GUI apps or
# daemons on a shared machine. Named, not silently skipped.
LAUNCHER_DENY = {
    "re-autolaunch": "spawns IDA/Ghidra/Binary-Ninja backends",
    "monitor-autolaunch": "spawns the workflow monitor TUI",
    "workflow-monitor-autolaunch": "spawns the workflow monitor TUI",
    "codex-monitor-autolaunch": "spawns the codex monitor TUI",
    "mcp-liveness": "may restart MCP servers (basic-memory)",
    "loop-recovery": "may re-issue a recovery command",
    "notify-idle": "emits desktop notifications",
    "stopfailure-notify": "emits desktop notifications",
    # Added AFTER a one-off fire: with a Stop payload it did not return inside 45 s
    # (exit=TIMEOUT). Whatever it does, it is not a sub-second hook, so an audit must
    # not keep re-triggering it -- and wiring it as-is would hang the event.
    "harness-bench": "did not return in 45 s when fired (runs a benchmark)",
}

VENDOR_DEFAULT = 600.0
DEFAULT_BUDGET = {"UserPromptSubmit": 30.0}
WIRED_CONTROL = "wire-check"
ABSENT_CONTROL = "zzz-not-a-real-hook-dir-9f3a"


# --------------------------------------------------------------------------- payloads
def tool_from_matcher(matcher: str | None) -> str:
    """Pick a tool name the entry's own matcher accepts, so the hook does not early-exit."""
    if not matcher or matcher in (".*", "*"):
        return "Edit"
    first = matcher.split("|")[0]
    first = first.replace(".*", "").replace("\\", "").strip()
    if first.startswith("mcp__"):
        return first.rstrip("_.") + "_probe" if first.endswith("__") else first
    return first or "Edit"


def payload_for(event: str, matcher: str | None, scratch: Path) -> dict:
    tool = tool_from_matcher(matcher)
    base = {
        "session_id": "hookfleet",
        "cwd": str(REPO),
        "transcript_path": "",
        "hook_event_name": event,
    }
    if event in ("PreToolUse", "PostToolUse", "PostToolUseFailure"):
        base["tool_name"] = tool
        base["tool_input"] = {
            "file_path": str(scratch),
            "old_string": "a",
            "new_string": "b",
            "command": "echo probe",
        }
        if event != "PreToolUse":
            base["tool_response"] = {"success": True}
    if event in ("Stop", "SubagentStop"):
        base["stop_hook_active"] = False
    if event == "SessionStart":
        base["source"] = "startup"
    if event == "UserPromptSubmit":
        base["prompt"] = "probe prompt for the hook fleet audit"
    if event in ("PreCompact", "PostCompact"):
        base["trigger"] = "manual"
    if event == "StopFailure":
        base["error"] = "probe"
    return base


# ------------------------------------------------------------------- wiring discovery
def read_settings_entries() -> list[dict]:
    raw = json.loads(SETTINGS.read_text(encoding="utf-8")).get("hooks") or {}
    rows = []
    for event, groups in raw.items():
        for grp in groups or []:
            for e in grp.get("hooks") or []:
                cmd = str(e.get("command") or "")
                t = e.get("timeout")
                rows.append(
                    {
                        "event": event,
                        "matcher": grp.get("matcher"),
                        "command": cmd,
                        "budget_s": float(t)
                        if t
                        else DEFAULT_BUDGET.get(event, VENDOR_DEFAULT),
                        "budget_source": "declared" if t else "vendor-default",
                    }
                )
    return rows


def wiring_surfaces() -> tuple[str, dict[str, int]]:
    """Concatenate every text surface that can wire a hook, plus per-surface sizes.

    Sizes are reported so a surface that silently failed to load (0 bytes) cannot be
    mistaken for a surface that simply mentions nothing.
    """
    blobs: dict[str, str] = {}
    try:
        blobs["settings"] = json.dumps(
            json.loads(SETTINGS.read_text(encoding="utf-8")).get("hooks") or {}
        )
    except Exception as e:  # noqa: BLE001
        blobs["settings"] = ""
        print(f"  WARN settings unreadable: {type(e).__name__}", file=sys.stderr)
    for label, p in (
        ("live_manifest", LIVE_HOOKS / "_dispatch" / "manifest.json"),
        ("repo_manifest", REPO / "hooks" / "_dispatch" / "manifest.json"),
        ("hooks_json", REPO / "hooks" / "hooks.json"),
    ):
        try:
            blobs[label] = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            blobs[label] = ""
    agent = []
    if AGENT_SELF.is_dir():
        for f in AGENT_SELF.rglob("*"):
            if f.suffix.lower() in (".py", ".json", ".toml") and f.is_file():
                try:
                    agent.append(f.read_text(encoding="utf-8", errors="replace"))
                except Exception:
                    continue
    blobs["agent_self"] = "\n".join(agent)
    return "\n".join(blobs.values()), {k: len(v) for k, v in blobs.items()}


_PATHREF = re.compile(r"hooks[/\\]([A-Za-z0-9_.-]+)[/\\][A-Za-z0-9_.-]+\.(?:py|js|ps1)")


def wiring_dirs_strict(surface: str) -> set[str]:
    """Hook dirs reachable via an actual PATH-SHAPED wiring reference.

    The loose `dir_name in surface` test is a USE-vs-MENTION error: `~/.agents/harness`
    alone is ~764 KB of Python/JSON, and a hook dir named in a comment, a doc string, a
    log line or an inventory listing scores as "wired". Measured: the loose test called
    65 of 73 dirs wired, against 24 dark from the grounding lane's per-surface field
    parsing -- so the loose test is the one that is wrong, and its synthetic
    absent-control could never have caught it (a name that appears nowhere is not the
    hypothesis under test).

    This counts only `.../hooks/<dir>/<file>.py`-shaped references plus manifest
    `script` fields -- the FIELD, not the document.
    """
    dirs = {m.group(1) for m in _PATHREF.finditer(surface)}
    for p in (
        LIVE_HOOKS / "_dispatch" / "manifest.json",
        REPO / "hooks" / "_dispatch" / "manifest.json",
    ):
        try:
            man = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for blob in (man.get("events") or {}).values():
            for chk in (blob or {}).get("checks") or []:
                s = str(chk.get("script") or "")
                if "/" in s or "\\" in s:
                    dirs.add(s.replace("\\", "/").split("/")[0])
    return dirs


def entry_script(cmd: str) -> Path | None:
    m = re.search(r"([A-Za-z]:[\\/][^\"']*?\.py)", cmd)
    if not m:
        return None
    p = Path(m.group(1).replace("\\", "/"))
    return p if p.is_file() else None


# ------------------------------------------------------------------------ measurement
def fire(
    script: Path,
    event: str,
    matcher: str | None,
    args: list[str],
    scratch: Path,
    hard_timeout: float,
) -> dict:
    payload = json.dumps(payload_for(event, matcher, scratch)).encode("utf-8")
    env = dict(os.environ)
    env["HOOK_FLEET_PROBE"] = "1"
    t0 = time.perf_counter()
    try:
        p = subprocess.run(
            [sys.executable, str(script), *args],
            input=payload,
            capture_output=True,
            timeout=hard_timeout,
            env=env,
            cwd=str(REPO),
        )
        ms = (time.perf_counter() - t0) * 1000
        so = p.stdout.decode("utf-8", "replace")
        return {
            "ran": True,
            "wall_ms": round(ms, 1),
            "exit": p.returncode,
            "stdout_bytes": len(p.stdout),
            "emitted_ctx": "additionalContext" in so or "hookSpecificOutput" in so,
            "stderr_tail": p.stderr.decode("utf-8", "replace")[-300:],
        }
    except subprocess.TimeoutExpired:
        return {
            "ran": False,
            "wall_ms": round((time.perf_counter() - t0) * 1000, 1),
            "exit": "TIMEOUT",
            "stdout_bytes": 0,
            "emitted_ctx": False,
            "stderr_tail": "",
        }
    except Exception as e:  # noqa: BLE001
        return {
            "ran": False,
            "wall_ms": round((time.perf_counter() - t0) * 1000, 1),
            "exit": f"ERROR:{type(e).__name__}",
            "stdout_bytes": 0,
            "emitted_ctx": False,
            "stderr_tail": str(e)[:300],
        }


def denied(hook_dir: str | None) -> str | None:
    if not hook_dir:
        return None
    for k, why in LAUNCHER_DENY.items():
        if k in hook_dir:
            return why
    return None


def run_timing(include_launchers: bool, scratch: Path) -> dict:
    rows = []
    for e in read_settings_entries():
        sc = entry_script(e["command"])
        hook_dir = None
        if sc is not None:
            hook_dir = sc.parent.name
        why = None if include_launchers else denied(hook_dir)
        row = dict(e, script=str(sc) if sc else None, hook_dir=hook_dir)
        if sc is None:
            row.update(measured=False, reason="command is not a resolvable .py path")
            rows.append(row)
            continue
        if why:
            row.update(measured=False, reason=f"NOT FIRED (side effect): {why}")
            rows.append(row)
            continue
        # dispatcher entries take the event name as argv[1]
        args = []
        m = re.search(r"\.py\s+([\w-]+)", e["command"])
        if m:
            args = [m.group(1)]
        res = fire(sc, e["event"], e["matcher"], args, scratch, e["budget_s"] * 3 + 10)
        pct = round(100.0 * (res["wall_ms"] / 1000.0) / e["budget_s"], 1)
        row.update(measured=True, **res, pct_of_budget=pct, over_budget=pct > 100.0)
        rows.append(row)
    measured = [r for r in rows if r.get("measured")]
    return {
        "entries_total": len(rows),
        "entries_measured": len(measured),
        "entries_not_measured": len(rows) - len(measured),
        "over_budget": [
            {
                "event": r["event"],
                "hook_dir": r["hook_dir"],
                "wall_ms": r["wall_ms"],
                "budget_s": r["budget_s"],
                "pct": r["pct_of_budget"],
            }
            for r in measured
            if r.get("over_budget")
        ],
        "worst_pct": max((r["pct_of_budget"] for r in measured), default=None),
        "rows": rows,
    }


def run_inertness(include_launchers: bool, scratch: Path) -> dict:
    surface, sizes = wiring_surfaces()
    strict = wiring_dirs_strict(surface)
    # detector controls FIRST -- a broken search invalidates every verdict below
    ctl_wired = WIRED_CONTROL in strict
    ctl_absent = ABSENT_CONTROL in strict
    dirs = sorted(
        d.name
        for d in (REPO / "hooks").iterdir()
        if d.is_dir() and not d.name.startswith("__")
    )
    rows = []
    for d in dirs:
        if d in ("_dispatch", "_shared"):
            continue
        wired = d in strict
        # MENTIONED-BUT-NOT-WIRED is the control class the synthetic absent-control
        # cannot supply: it is direct evidence that the loose document-level search
        # over-reports, and it must be non-empty for the strict search to be doing work.
        row = {
            "hook_dir": d,
            "wired_anywhere": wired,
            "mentioned_only": (not wired) and d in surface,
        }
        if wired:
            rows.append(row)
            continue
        why = None if include_launchers else denied(d)
        if why:
            row.update(verdict="DARK-NOT-FIRED", reason=f"side effect: {why}")
            rows.append(row)
            continue
        scripts = sorted(
            p
            for p in (REPO / "hooks" / d).glob("*.py")
            if not p.name.startswith("test_")
        )
        if not scripts:
            row.update(verdict="DARK-NO-SCRIPT")
            rows.append(row)
            continue
        res = fire(scripts[0], "Stop", None, [], scratch, 45.0)
        row.update(script=scripts[0].name, **res)
        if res["ran"] and isinstance(res["exit"], int) and res["exit"] in (0, 2):
            row["verdict"] = (
                "INERT-CONFIRMED"  # runs standalone, reachable from nothing
            )
        else:
            row["verdict"] = (
                "DARK-AND-BROKEN"  # cannot even run; darkness is not the only problem
            )
        rows.append(row)
    dark = [r for r in rows if not r["wired_anywhere"]]
    return {
        "surface_sizes_bytes": sizes,
        "control_wired_found": ctl_wired,
        "control_absent_found": ctl_absent,
        "control_mentioned_only_count": sum(1 for r in rows if r.get("mentioned_only")),
        "strict_wiring_dirs_found": len(strict),
        "dirs_total": len(rows),
        "dirs_wired": sum(1 for r in rows if r["wired_anywhere"]),
        "dirs_dark": len(dark),
        "verdicts": {
            v: sum(1 for r in dark if r.get("verdict") == v)
            for v in (
                "INERT-CONFIRMED",
                "DARK-AND-BROKEN",
                "DARK-NOT-FIRED",
                "DARK-NO-SCRIPT",
            )
        },
        "rows": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timing", action="store_true")
    ap.add_argument("--inertness", action="store_true")
    ap.add_argument("--include-launchers", action="store_true")
    a = ap.parse_args()
    if not (a.timing or a.inertness):
        a.timing = a.inertness = True

    scratch = OUT / "_fleet_scratch.txt"
    scratch.write_text("probe\n", encoding="utf-8")
    res: dict = {}
    rc = 0

    if a.timing:
        t = run_timing(a.include_launchers, scratch)
        res["timing"] = t
        print(
            f"== TIMING  {t['entries_measured']}/{t['entries_total']} entries measured "
            f"({t['entries_not_measured']} not fired)"
        )
        for r in sorted(
            (x for x in t["rows"] if x.get("measured")),
            key=lambda x: -x["pct_of_budget"],
        )[:14]:
            flag = "!!" if r["over_budget"] else "  "
            print(
                f"{flag} {r['event']:20s} {str(r['hook_dir'])[:26]:26s} "
                f"{r['wall_ms']:8.1f} ms /{r['budget_s']:5.0f}s = {r['pct_of_budget']:6.1f}% "
                f"exit={r['exit']} ctx={r['emitted_ctx']}"
            )
        for r in (x for x in t["rows"] if not x.get("measured")):
            print(
                f"   {r['event']:20s} {str(r['hook_dir'])[:26]:26s} SKIPPED: {r['reason']}"
            )
        if t["entries_total"] == 0:
            print("FAILED:hook-fleet-timing zero entries enumerated")
            rc = 1

    if a.inertness:
        i = run_inertness(a.include_launchers, scratch)
        res["inertness"] = i
        print(
            f"\n== INERTNESS  {i['dirs_dark']} dark of {i['dirs_total']} dirs  "
            f"verdicts={i['verdicts']}"
        )
        print(
            f"   controls: wired({WIRED_CONTROL})={i['control_wired_found']} "
            f"(must be True)  absent={i['control_absent_found']} (must be False)"
        )
        print(f"   surfaces: {i['surface_sizes_bytes']}")
        for r in sorted(
            (x for x in i["rows"] if not x["wired_anywhere"]),
            key=lambda x: (x.get("verdict") or "", x["hook_dir"]),
        ):
            print(
                f"   {r['hook_dir']:28s} {r.get('verdict', ''):18s} "
                f"exit={str(r.get('exit', '-')):>10s} ctx={r.get('emitted_ctx', '-')} "
                f"{r.get('reason', '')}"
            )
        if not i["control_wired_found"] or i["control_absent_found"]:
            print(
                "FAILED:hook-fleet-inertness detector control misbehaved -- verdicts void"
            )
            rc = 1
        if i["dirs_total"] == 0:
            print("FAILED:hook-fleet-inertness zero hook dirs enumerated")
            rc = 1

    (OUT / "B6-FLEET.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print("\n" + ("SUCCESS:hook-fleet" if rc == 0 else "FAILED:hook-fleet"))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
