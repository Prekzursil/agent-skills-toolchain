"""Write the live command/skill/monitor/script trees and the usage ledger."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
LIVE = FIX / "live"
LEDGER = FIX / "usage-ledger.jsonl"

COMMANDS = {
    "/run": "Product command. Run a workflow, council, or skill through one entry.",
    "/cockpit": "Product cockpit. Fleet, status, and ops in one surface.",
    "/catalog": "Product catalog. Discover workflows and presets.",
    "/council": "Legacy council launcher. Muscle-memory name.",
    "/wf": "Short workflow launcher.",
    "/workflow": "Long workflow launcher.",
    "/status": "Legacy status view.",
    "/dash": "Legacy dashboard.",
    "/help": "Legacy help / discovery.",
    "/old-repair": "Legacy repair path. Still used; warn on invoke.",
    "/sync-live": "One-directional live sync. Warn; do not silently overwrite.",
    "/tmp-scratch": "One-off scratch command. Zero usage in the observation window.",
}

SKILLS = {
    "skill.catalog": "Catalog discovery skill backing /catalog.",
    "skill.council": "Council skill. Routes to /run.",
    "skill.debug-dump": "Debug dump skill. Deprecated.",
    "skill.scratch": "Scratch skill. Zero usage in the observation window.",
}

MONITORS = {
    "monitor.fleet": {"description": "Fleet monitor. Routes to /cockpit."},
    "monitor.heartbeat-legacy": {"description": "Legacy heartbeat. Deprecated."},
}

SCRIPTS = {
    "scripts/run-council.py": "#!/usr/bin/env python3\n# name: scripts/run-council.py\nprint('legacy council script')\n",
    "scripts/sync-from-live.ps1": "# name: scripts/sync-from-live.ps1\nWrite-Output 'legacy one-directional sync'\n",
    "scripts/adhoc-once.sh": "#!/bin/sh\n# name: scripts/adhoc-once.sh\necho adhoc\n",
}

# Observed invocations. Dates inside 2026-08-10 .. 2026-08-24 count; earlier do not.
USAGE_EVENTS: list[tuple[str, str, str]] = [
    ("/run", "2026-08-12T10:00:00Z", "transcript"),
    ("/run", "2026-08-13T10:00:00Z", "transcript"),
    ("/run", "2026-08-15T11:00:00Z", "transcript"),
    ("/run", "2026-08-18T09:00:00Z", "transcript"),
    ("/run", "2026-08-20T09:00:00Z", "transcript"),
    ("/run", "2026-08-22T09:00:00Z", "transcript"),
    ("/cockpit", "2026-08-14T08:00:00Z", "transcript"),
    ("/cockpit", "2026-08-19T08:00:00Z", "transcript"),
    ("/cockpit", "2026-08-21T08:00:00Z", "transcript"),
    ("/catalog", "2026-08-16T12:00:00Z", "transcript"),
    ("/catalog", "2026-08-23T12:00:00Z", "transcript"),
    ("skill.catalog", "2026-08-17T13:00:00Z", "transcript"),
    ("skill.catalog", "2026-08-22T13:00:00Z", "transcript"),
    ("/council", "2026-08-11T15:00:00Z", "transcript"),
    ("/council", "2026-08-14T15:00:00Z", "transcript"),
    ("/council", "2026-08-18T15:00:00Z", "transcript"),
    ("/council", "2026-08-21T15:00:00Z", "transcript"),
    ("/wf", "2026-08-12T16:00:00Z", "transcript"),
    ("/wf", "2026-08-19T16:00:00Z", "transcript"),
    ("/wf", "2026-08-23T16:00:00Z", "transcript"),
    ("/workflow", "2026-08-13T17:00:00Z", "transcript"),
    ("/workflow", "2026-08-20T17:00:00Z", "transcript"),
    ("/status", "2026-08-11T18:00:00Z", "transcript"),
    ("/status", "2026-08-16T18:00:00Z", "transcript"),
    ("/status", "2026-08-22T18:00:00Z", "transcript"),
    ("/dash", "2026-08-15T19:00:00Z", "transcript"),
    ("/help", "2026-08-14T20:00:00Z", "transcript"),
    ("/help", "2026-08-21T20:00:00Z", "transcript"),
    ("skill.council", "2026-08-12T21:00:00Z", "transcript"),
    ("skill.council", "2026-08-18T21:00:00Z", "transcript"),
    ("skill.council", "2026-08-23T21:00:00Z", "transcript"),
    ("monitor.fleet", "2026-08-13T07:00:00Z", "monitor"),
    ("monitor.fleet", "2026-08-20T07:00:00Z", "monitor"),
    ("scripts/run-council.py", "2026-08-17T22:00:00Z", "script"),
    ("/old-repair", "2026-08-12T06:00:00Z", "transcript"),
    ("/old-repair", "2026-08-19T06:00:00Z", "transcript"),
    ("/sync-live", "2026-08-16T06:30:00Z", "transcript"),
    ("skill.debug-dump", "2026-08-11T05:00:00Z", "transcript"),
    ("skill.debug-dump", "2026-08-18T05:00:00Z", "transcript"),
    ("monitor.heartbeat-legacy", "2026-08-15T05:30:00Z", "monitor"),
    ("scripts/sync-from-live.ps1", "2026-08-21T05:45:00Z", "script"),
    # Pre-window only: must NOT count toward removal evidence.
    ("/tmp-scratch", "2026-07-01T00:00:00Z", "transcript"),
    ("skill.scratch", "2026-07-04T00:00:00Z", "transcript"),
    ("scripts/adhoc-once.sh", "2026-07-08T00:00:00Z", "script"),
]


def _slash_md(name: str, body: str) -> str:
    slug = name.lstrip("/")
    return (
        f"---\nname: {name}\nkind: slash-command\n---\n"
        f"# {name}\n\n{body}\n\nslug: {slug}\n"
    )


def _skill_md(name: str, body: str) -> str:
    return (
        f"---\nname: {name}\nkind: skill\n---\n"
        f"# {name}\n\n{body}\n"
    )


def write_live_tree(root: Path | None = None) -> Path:
    live = root or LIVE
    if live.exists():
        for p in live.rglob("*"):
            if p.is_file():
                p.unlink()
    (live / "commands").mkdir(parents=True, exist_ok=True)
    (live / "skills").mkdir(parents=True, exist_ok=True)
    (live / "monitors").mkdir(parents=True, exist_ok=True)
    (live / "scripts").mkdir(parents=True, exist_ok=True)
    for name, body in COMMANDS.items():
        slug = name.lstrip("/")
        (live / "commands" / f"{slug}.md").write_text(
            _slash_md(name, body), encoding="utf-8"
        )
    for name, body in SKILLS.items():
        d = live / "skills" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(_skill_md(name, body), encoding="utf-8")
    for name, meta in MONITORS.items():
        doc = {"id": name, "name": name, "kind": "monitor", **meta}
        (live / "monitors" / f"{name}.json").write_text(
            json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    for rel, text in SCRIPTS.items():
        (live / rel).write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    return live


def write_ledger(path: Path | None = None) -> Path:
    dest = path or LEDGER
    dest.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for name, ts, source in USAGE_EVENTS:
        lines.append(json.dumps({"name": name, "ts": ts, "source": source}, sort_keys=True))
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest


def main() -> int:
    live = write_live_tree()
    ledger = write_ledger()
    n_cmd = len(list((live / "commands").glob("*.md")))
    n_sk = len(list((live / "skills").glob("*/SKILL.md")))
    n_mo = len(list((live / "monitors").glob("*.json")))
    n_sc = len([p for p in (live / "scripts").iterdir() if p.is_file()])
    print(f"live commands={n_cmd} skills={n_sk} monitors={n_mo} scripts={n_sc}")
    print(f"ledger {ledger}")
    print("SUCCESS:ARC-0056 scenario")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
