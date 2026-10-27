#!/usr/bin/env python3
"""G5c: check the LIVE hook fleet against the VENDOR's documented per-event timeout caps
and blocking contract (code.claude.com/docs/en/hooks, fetched 2026-08-13).

Nobody in rounds 1-4 checked this axis. Round 4 computed check-budget vs EVENT-budget
*inside* our own dispatcher; this compares our DECLARED timeouts against the harness's own
documented ceilings, which are a different denominator again.

Vendor facts encoded here (each tagged with its doc claim so a doc change invalidates loudly):
  V1  timeout is PER-HOOK-COMMAND; a timed-out hook is cancelled individually and renders no
      decision; OTHER hooks on the event keep running.
      -> our dispatcher is ONE command holding N checks, so its single cancellation loses all N.
  V2  default timeouts: command/http/mcp_tool 600s; prompt 30s; agent 60s.
  V3  per-event LOWERED caps: UserPromptSubmit 30s; MessageDisplay 10s;
      SessionEnd hooks share a 1.5s budget (auto-raised to max 60s if individual timeouts need it).
  V4  `if` is evaluated ONLY on tool events (PreToolUse, PostToolUse, PostToolUseFailure,
      PermissionRequest, PermissionDenied). On any OTHER event a hook with `if` NEVER RUNS.
  V5  exit 2 blocks on blocking events; exit 1 is NON-blocking for most events;
      PermissionRequest ignores exit 2 (needs a JSON decision object);
      WorktreeCreate fails on ANY non-zero exit.

SECURITY: settings.json holds live credentials. This reads ONLY the `hooks` subtree and
prints event names, timeouts and command BASENAMES. No values, no env, no full commands.
"""

import json
import re
import sys

LIVE_SETTINGS = r"C:\Users\Prekzursil\.claude\settings.json"

# V3 — documented per-event ceilings that OVERRIDE the 600s default
EVENT_CAP_S = {
    "UserPromptSubmit": 30.0,
    "MessageDisplay": 10.0,
    "SessionEnd": 1.5,  # shared budget; auto-raise to <=60 if individual timeouts demand
}
SESSIONEND_AUTORAISE_MAX_S = 60.0

# V4 — the ONLY events where `if` is evaluated
IF_EVALUATED_EVENTS = {
    "PreToolUse",
    "PostToolUse",
    "PostToolUseFailure",
    "PermissionRequest",
    "PermissionDenied",
}

# V5 — events where exit 2 does NOT block (a hook relying on it is inert as a gate)
EXIT2_IGNORED_EVENTS = {
    "PermissionRequest",
    "PostToolUse",
    "PostToolUseFailure",
    "StopFailure",
    "Notification",
    "SessionStart",
    "Setup",
    "SessionEnd",
    "CwdChanged",
    "DirectoryAdded",
    "FileChanged",
    "WorktreeRemove",
    "PostCompact",
    "InstructionsLoaded",
    "MessageDisplay",
}

VENDOR_EVENTS = {
    "SessionStart",
    "SessionEnd",
    "Setup",
    "UserPromptSubmit",
    "UserPromptExpansion",
    "Stop",
    "StopFailure",
    "PreToolUse",
    "PostToolUse",
    "PostToolUseFailure",
    "PermissionRequest",
    "PermissionDenied",
    "PostToolBatch",
    "SubagentStart",
    "SubagentStop",
    "TaskCreated",
    "TaskCompleted",
    "InstructionsLoaded",
    "ConfigChange",
    "CwdChanged",
    "DirectoryAdded",
    "FileChanged",
    "PreCompact",
    "PostCompact",
    "Notification",
    "MessageDisplay",
    "TeammateIdle",
    "Elicitation",
    "ElicitationResult",
    "WorktreeCreate",
    "WorktreeRemove",
}


def basename_of(cmd):
    if not isinstance(cmd, str):
        return f"<{type(cmd).__name__}>"
    m = re.findall(r"[\w.\-]+\.(?:py|ps1|sh|cmd|exe|mjs|js)", cmd)
    return m[-1] if m else (cmd.split()[0][:40] if cmd.split() else "?")


def main():
    with open(LIVE_SETTINGS, encoding="utf-8") as f:
        st = json.load(f)
    hooks = st.get("hooks") or {}

    rows = []
    for ev, groups in hooks.items():
        for g in groups or []:
            matcher = g.get("matcher")
            for h in g.get("hooks") or []:
                rows.append(
                    {
                        "event": ev,
                        "matcher": matcher,
                        "type": h.get("type", "command"),
                        "timeout": h.get("timeout"),
                        "has_if": "if" in h,
                        "if": h.get("if"),
                        "script": basename_of(h.get("command")),
                    }
                )

    res = {"total_entries": len(rows), "events_used": sorted(hooks.keys())}

    # ---- CONTROL: the detector must find a KNOWN-PRESENT shape before its silence counts.
    # We know from rounds 1-4 that all 42 entries declare a timeout. If we parse 0 timeouts,
    # the shape moved and every "no violation" below is meaningless.
    with_timeout = [r for r in rows if isinstance(r["timeout"], (int, float))]
    res["control_entries_parsed"] = len(rows)
    res["control_entries_with_numeric_timeout"] = len(with_timeout)
    res["control_shape_ok"] = len(rows) >= 20 and len(with_timeout) >= 20
    if not res["control_shape_ok"]:
        res["control_note"] = (
            "FAIL-CLOSED: parsed too few entries/timeouts; the settings shape moved. "
            "No verdict below may be cited."
        )
        print(json.dumps(res, indent=2))
        return 1

    # ---- V3: declared timeout vs documented per-event cap
    cap_violations = []
    for r in rows:
        cap = EVENT_CAP_S.get(r["event"])
        if cap is None:
            continue
        t = r["timeout"]
        if not isinstance(t, (int, float)):
            continue
        if r["event"] == "SessionEnd":
            # shared 1.5s budget, auto-raised to at most 60s
            if t > SESSIONEND_AUTORAISE_MAX_S:
                cap_violations.append(
                    {
                        **r,
                        "cap_s": SESSIONEND_AUTORAISE_MAX_S,
                        "kind": "SessionEnd declared above the 60s auto-raise max",
                    }
                )
            elif t > cap:
                cap_violations.append(
                    {
                        **r,
                        "cap_s": cap,
                        "kind": "SessionEnd declares more than the 1.5s shared budget "
                        "(vendor auto-raises, but the 1.5s default is what an "
                        "undeclared sibling gets)",
                    }
                )
        elif t > cap:
            cap_violations.append(
                {
                    **r,
                    "cap_s": cap,
                    "kind": "declared timeout EXCEEDS the documented event cap; "
                    "the cap wins, so the declared budget is fiction",
                }
            )
    res["V3_cap_violations"] = cap_violations
    res["V3_cap_violation_count"] = len(cap_violations)

    # ---- V4: `if` on a non-tool event => the hook NEVER RUNS
    if_dead = [r for r in rows if r["has_if"] and r["event"] not in IF_EVALUATED_EVENTS]
    if_live = [r for r in rows if r["has_if"] and r["event"] in IF_EVALUATED_EVENTS]
    res["V4_if_used_total"] = sum(1 for r in rows if r["has_if"])
    res["V4_if_on_non_tool_event_DEAD"] = if_dead
    res["V4_if_on_tool_event_ok"] = len(if_live)

    # ---- V5: which entries sit on events where exit 2 cannot block
    res["V5_entries_on_exit2_ignored_events"] = sorted(
        {
            (r["event"] + "/" + r["script"])
            for r in rows
            if r["event"] in EXIT2_IGNORED_EVENTS
        }
    )
    res["V5_count"] = len(res["V5_entries_on_exit2_ignored_events"])

    # ---- unknown / unused event surface
    used = set(hooks.keys())
    res["events_not_in_vendor_list"] = sorted(used - VENDOR_EVENTS)
    res["vendor_events_unused"] = sorted(VENDOR_EVENTS - used)
    res["vendor_events_unused_count"] = len(res["vendor_events_unused"])

    # ---- timeout distribution per event (no values, just budgets)
    per_event = {}
    for r in rows:
        per_event.setdefault(r["event"], []).append(r["timeout"])
    res["declared_timeouts_by_event"] = {
        k: sorted(v, key=lambda x: (x is None, x)) for k, v in sorted(per_event.items())
    }

    print(json.dumps(res, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
