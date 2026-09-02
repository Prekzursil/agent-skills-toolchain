#!/usr/bin/env python3
"""Is the checkpoint pair actually WIRED? Check-only, plus the exact patch to apply.

    python wire.py --check          # typed verdict for each half
    python wire.py --print-patch    # the exact JSON to add (copy/paste or jq)

THERE IS DELIBERATELY NO `--apply`.
    `~/.claude/settings.json` and `hooks/_dispatch/manifest.json` are owned by other lanes, and
    seven agents share one filesystem in this program. A read-modify-write of a shared JSON file
    from a lane that does not own it is how a sibling's edit gets silently reverted. Wiring is an
    OWNER action; this script's job is to make it a one-paste action and to tell you, honestly,
    whether it has happened.

WHY THIS SCRIPT IS PART OF THE DELIVERABLE
    A hook that exists on disk and is registered nowhere is the exact GREEN-not-LIVE defect this
    estate keeps re-discovering: `hooks/precompact-snapshot/snapshot.ps1`,
    `hooks/precompact-basicmemory/capture.ps1` and `hooks/event-ledger/sessionstart-replay.py`
    are all on disk right now and wired to nothing. Shipping the checker alongside the hook is
    what stops this pair from joining them. `recover.py`'s FINDING state is the runtime half of
    the same guarantee.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HOME = Path(os.path.expanduser("~"))
DEFAULT_SETTINGS = HOME / ".claude" / "settings.json"
DEFAULT_MANIFEST = HOME / ".claude" / "hooks" / "_dispatch" / "manifest.json"

PRECOMPACT_TOKEN = "hooks/checkpoint/precompact.py"
RECOVER_TOKEN = "hooks/checkpoint/recover.py"
RECOVER_CHECK = "checkpoint/recover.py"

PRECOMPACT_ENTRY = {
    "matcher": ".*",
    "hooks": [
        {
            "type": "command",
            "command": 'python "C:/Users/Prekzursil/.claude/hooks/checkpoint/precompact.py"',
            "timeout": 10,
            "statusMessage": "Checkpoint: write execution state",
        }
    ],
}

SESSIONSTART_ENTRY = {
    "matcher": ".*",
    "hooks": [
        {
            "type": "command",
            "command": 'python "C:/Users/Prekzursil/.claude/hooks/checkpoint/recover.py"',
            "timeout": 10,
            "statusMessage": "Checkpoint: recover execution state",
        }
    ],
}

DISPATCH_CHECK = {
    "name": "checkpoint/recover",
    "script": "checkpoint/recover.py",
    "args": [],
    "timeout": 8,
    "isolate": None,
    "side_effect": "none",
    "emits": True,
    "comment": (
        "SessionStart half of the compaction-survival pair. Reads .beads/context/"
        "execution-state.md written by hooks/checkpoint/precompact.py and injects it on a "
        "resume/compact/clear start. Emits FINDING when a recovery-path start finds NO "
        "checkpoint -- that is the dead-man switch for the PreCompact half, so do NOT wire this "
        "without also wiring precompact.py in settings.json (the dispatcher has no PreCompact "
        "alias: _dispatch/dispatch.py:108-115). Injects only, never blocks, fail-open. "
        "Opt-out: hooks/checkpoint/.disabled."
    ),
}


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def check(settings_path: Path, manifest_path: Path) -> list[tuple[str, str, str]]:
    """[(half, typed_state, detail)] -- NOT-CHECKED when the surface itself is unreadable."""
    out: list[tuple[str, str, str]] = []

    settings = _load(settings_path)
    if settings is None:
        out.append(("PreCompact", "NOT-CHECKED", f"cannot read {settings_path}"))
        out.append(
            ("SessionStart(settings)", "NOT-CHECKED", f"cannot read {settings_path}")
        )
    else:
        blob = json.dumps(settings.get("hooks", {}).get("PreCompact", []))
        out.append(
            (
                "PreCompact",
                "WIRED"
                if PRECOMPACT_TOKEN in blob.replace("\\\\", "/").replace("\\", "/")
                else "NOT-WIRED",
                f"{settings_path} hooks.PreCompact",
            )
        )
        blob = json.dumps(settings.get("hooks", {}).get("SessionStart", []))
        out.append(
            (
                "SessionStart(settings)",
                "WIRED"
                if RECOVER_TOKEN in blob.replace("\\\\", "/").replace("\\", "/")
                else "NOT-WIRED",
                f"{settings_path} hooks.SessionStart",
            )
        )

    manifest = _load(manifest_path)
    if manifest is None:
        out.append(
            ("SessionStart(dispatch)", "NOT-CHECKED", f"cannot read {manifest_path}")
        )
    else:
        checks = manifest.get("events", {}).get("SessionStart", {}).get("checks", [])
        hit = any(
            str(c.get("script", "")).replace("\\", "/") == RECOVER_CHECK for c in checks
        )
        out.append(
            (
                "SessionStart(dispatch)",
                "WIRED" if hit else "NOT-WIRED",
                f"{manifest_path} events.SessionStart.checks",
            )
        )
    return out


def summarize(rows: list[tuple[str, str, str]]) -> tuple[str, str]:
    states = {half: st for half, st, _ in rows}
    pre = states.get("PreCompact", "NOT-CHECKED")
    rec_wired = "WIRED" in (
        states.get("SessionStart(settings)"),
        states.get("SessionStart(dispatch)"),
    )
    rec_unknown = "NOT-CHECKED" in (
        states.get("SessionStart(settings)"),
        states.get("SessionStart(dispatch)"),
    )

    if pre == "NOT-CHECKED" or (rec_unknown and not rec_wired):
        return (
            "NOT-CHECKED",
            "at least one wiring surface could not be read; this is not a pass",
        )
    if pre == "WIRED" and rec_wired:
        return "CLEAN", "both halves are wired"
    if pre == "WIRED" and not rec_wired:
        return (
            "FINDING",
            "the WRITER is wired and the READER is not -- this is the 101-files-0-readers shape",
        )
    if rec_wired and pre != "WIRED":
        return (
            "FINDING",
            "the READER is wired and the WRITER is not -- recovery will fire FINDING on every resume",
        )
    return "FINDING", "NEITHER half is wired: the hook is on disk and live nowhere"


def print_patch() -> None:
    print(
        "# 1. PreCompact WRITER -> ~/.claude/settings.json, append to hooks.PreCompact"
    )
    print(
        "#    (this MUST be a settings.json entry: _dispatch/dispatch.py:108-115 `_EVENT_ALIASES`"
    )
    print(
        "#     has no `precompact` key, so the dispatcher cannot route the event at all.)"
    )
    print(json.dumps(PRECOMPACT_ENTRY, indent=2))
    print()
    print(
        "# 2. SessionStart READER -- PREFERRED: one line in hooks/_dispatch/manifest.json,"
    )
    print(
        "#    events.SessionStart.checks (matches the manifest's own 'adding a future check ="
    )
    print("#    one line here' contract; runs in-process, no extra interpreter spawn).")
    print(json.dumps(DISPATCH_CHECK, indent=2))
    print()
    print("# 2b. SessionStart READER -- ALTERNATIVE if you prefer a standalone entry:")
    print(json.dumps(SESSIONSTART_ENTRY, indent=2))
    print()
    print("# 3. Verify:  python hooks/checkpoint/wire.py --check     -> expect CLEAN")
    print(
        "#    Then force a manual /compact and confirm .beads/context/execution-state.md appears."
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--print-patch", action="store_true")
    ap.add_argument("--settings", default=str(DEFAULT_SETTINGS))
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    args = ap.parse_args(argv)

    if args.print_patch:
        print_patch()
        return 0

    rows = check(Path(args.settings), Path(args.manifest))
    for half, st, detail in rows:
        print(f"{st:<12} {half:<24} {detail}")
    verdict, why = summarize(rows)
    print()
    print(
        f"{'SUCCESS:' if verdict == 'CLEAN' else 'FAILED:'}checkpoint-wiring {verdict} — {why}"
    )
    if verdict != "CLEAN":
        print(
            "Run `python wire.py --print-patch` for the exact JSON. There is no --apply by design."
        )
    return 0 if verdict == "CLEAN" else 1


if __name__ == "__main__":
    sys.exit(main())
