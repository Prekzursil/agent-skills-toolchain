#!/usr/bin/env python3
"""G5d: cross the 11 known BLOCKERS (H9-BLOCK-CENSUS.json) against the EVENT each is wired to,
then against the vendor's documented blocking contract.

H9 established WHICH files can block. It did not record WHERE they are wired, so the question
"is this blocker sitting on an event where blocking is IGNORED?" has never been asked. A
blocker on PostToolUse/PermissionRequest is a gate that cannot go red -- the exact class this
audit is about.

Vendor contract (code.claude.com/docs/en/hooks, fetched 2026-08-13):
  exit 2 BLOCKS on: PreToolUse, UserPromptSubmit, UserPromptExpansion, Stop, SubagentStop,
    TeammateIdle, TaskCreated, TaskCompleted, ConfigChange, PostToolBatch, PreCompact,
    Elicitation, ElicitationResult; WorktreeCreate fails on ANY non-zero.
  exit 2 IGNORED on: PermissionRequest (needs a JSON decision object instead), PostToolUse,
    PostToolUseFailure, StopFailure, Notification, SessionStart, Setup, SessionEnd,
    CwdChanged, DirectoryAdded, FileChanged, WorktreeRemove, PostCompact,
    InstructionsLoaded, MessageDisplay.

CONTROLS (both states, per single-signal-verification 3b/3c):
  K1 POSITIVE: deny-credential-reads (H9's own block control) must resolve to >=1 event.
     If the resolver cannot place a blocker we KNOW is wired, its silence about the others
     is a resolver failure, not a finding.
  K2 NEGATIVE: a synthetic blocker name that is wired nowhere must resolve to 0 events.
  K3 DISCRIMINATION: the two arms must differ. If K1 and K2 both return the same count the
     resolver has measured nothing and the run publishes INCONCLUSIVE.
"""

import json
import sys

LIVE_SETTINGS = r"C:\Users\Prekzursil\.claude\settings.json"
LIVE_MANIFEST = r"C:\Users\Prekzursil\.claude\hooks\_dispatch\manifest.json"
REPO_MANIFEST = (
    r"C:\Users\Prekzursil\source\ast-integrate\hooks\_dispatch\manifest.json"
)
CENSUS = r"C:\Users\Prekzursil\source\ast-integrate\command-center\hook-audit\H9-BLOCK-CENSUS.json"

EXIT2_BLOCKS = {
    "PreToolUse",
    "UserPromptSubmit",
    "UserPromptExpansion",
    "Stop",
    "SubagentStop",
    "TeammateIdle",
    "TaskCreated",
    "TaskCompleted",
    "ConfigChange",
    "PostToolBatch",
    "PreCompact",
    "Elicitation",
    "ElicitationResult",
    "WorktreeCreate",
}
EXIT2_IGNORED = {
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


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def wiring_index():
    """Build {event: [haystack strings]} from settings.json commands + manifest check scripts."""
    idx = {}
    st = load(LIVE_SETTINGS)
    for ev, groups in (st.get("hooks") or {}).items():
        for g in groups or []:
            for h in g.get("hooks") or []:
                cmd = h.get("command")
                if isinstance(cmd, str):
                    idx.setdefault(ev, []).append(cmd.replace("\\", "/"))
    for label, path in (("live", LIVE_MANIFEST), ("repo", REPO_MANIFEST)):
        m = load(path)
        for ev, val in (m.get("events") or {}).items():
            checks = val.get("checks") if isinstance(val, dict) else val
            for c in checks or []:
                if isinstance(c, dict):
                    s = c.get("script") or ""
                    idx.setdefault(f"{ev}", []).append(
                        str(s).replace("\\", "/") + f"  #{label}"
                    )
    return idx


def resolve(needle, idx):
    """needle like 'per-edit-check/check.py' -> events whose wiring text contains it."""
    n = needle.replace("\\", "/").lower()
    hits = []
    for ev, hay in idx.items():
        for h in hay:
            if n in h.lower():
                hits.append(ev)
                break
    return sorted(set(hits))


def main():
    census = load(CENSUS)
    blockers = census["blockers"]
    idx = wiring_index()

    # ---- controls
    k1 = resolve("deny-credential-reads/deny.py", idx)
    k2 = resolve("zzz-synthetic-not-wired-anywhere/nope.py", idx)
    ctl = {
        "K1_positive_control_events": k1,
        "K1_positive_control_resolved": len(k1) >= 1,
        "K2_negative_control_events": k2,
        "K2_negative_control_absent": len(k2) == 0,
        "K3_arms_discriminate": len(k1) != len(k2),
    }
    if not (
        ctl["K1_positive_control_resolved"]
        and ctl["K2_negative_control_absent"]
        and ctl["K3_arms_discriminate"]
    ):
        print(
            json.dumps(
                {
                    "verdict": "INCONCLUSIVE - resolver failed its own controls",
                    "controls": ctl,
                },
                indent=2,
            )
        )
        return 1

    rows = []
    for b in blockers:
        evs = resolve(b, idx)
        ignored = [e for e in evs if e in EXIT2_IGNORED]
        blocks = [e for e in evs if e in EXIT2_BLOCKS]
        unknown = [e for e in evs if e not in EXIT2_IGNORED and e not in EXIT2_BLOCKS]
        if not evs:
            verdict = "UNWIRED-here (dark, or wired by module name not path)"
        elif ignored and not blocks:
            verdict = "DEAD-GATE: every event it is wired to IGNORES exit 2"
        elif ignored and blocks:
            verdict = "MIXED: blocks on some events, inert on others"
        else:
            verdict = "OK: wired only where blocking is honoured"
        rows.append(
            {
                "blocker": b,
                "events": evs,
                "exit2_ignored_on": ignored,
                "exit2_blocks_on": blocks,
                "unclassified": unknown,
                "verdict": verdict,
            }
        )

    res = {
        "controls": ctl,
        "blockers_examined": len(rows),
        "rows": rows,
        "dead_gates": [
            r["blocker"] for r in rows if r["verdict"].startswith("DEAD-GATE")
        ],
        "mixed": [r["blocker"] for r in rows if r["verdict"].startswith("MIXED")],
        "unwired": [r["blocker"] for r in rows if r["verdict"].startswith("UNWIRED")],
    }
    res["dead_gate_count"] = len(res["dead_gates"])
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
